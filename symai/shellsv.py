import glob
import logging
import os
import signal
import subprocess
import time
from typing import Iterable

from prompt_toolkit import HTML, PromptSession, print_formatted_text
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import CompleteStyle, ProgressBar
from prompt_toolkit.styles import Style
from pygments.lexers.shell import BashLexer

from .backend.settings import SYMSH_CONFIG
from .components import Function
from .extended import Conversation
from .misc.console import ConsoleStyle
from .misc.loader import Loader
from .symbol import Symbol
from .extended import DocumentRetriever, RepositoryCloner, FileMerger, ArxivPdfParser


logging.getLogger("prompt_toolkit").setLevel(logging.ERROR)


print = print_formatted_text


SHELL_CONTEXT = """[Description]
This shell program is the command interpreter on the Linux systems, MacOS and Windows PowerShell.
It is a program that interacts with the users in the terminal emulation window.
Shell commands are instructions that instruct the system to do some action.

[Program Instructions]
If user requests commands, you will only process user queries and return valid Linux/MacOS shell or Windows PowerShell commands and no other text.
If no further specified, use as default the Linux/MacOS shell commands.
If additional instructions are provided the follow the user query to produce the requested output.
A well related and helpful answer with suggested improvements is preferred over "I don't know" or "I don't understand" answers or stating the obvious.
"""


stateful_conversation = None


def supports_ansi_escape():
    try:
        os.get_terminal_size(0)
        return True
    except OSError:
        return False


class PathCompleter(Completer):
    def get_completions(self, document, complete_event):
        complete_word = document.get_word_before_cursor(WORD=True)
        sep = os.path.sep
        if complete_word.startswith(f'~{sep}'):
            complete_word = complete_word.replace(f'~{sep}', os.path.expanduser('~'))

        files = glob.glob(complete_word + '*')

        dirs_ = []
        files_ = []

        for file in files:
            # split the command into words by space (ignore escaped spaces)
            command_words = document.text.split(' ')
            if len(command_words) > 1:
                # Calculate start position of the completion
                start_position = len(document.text) - len(' '.join(command_words[:-1])) - 1
                start_position = max(0, start_position)
            else:
                start_position = len(document.text)
            # if there is a space in the file name, then escape it
            if ' ' in file:
                file = file.replace(' ', '\\ ')
            if (document.text.startswith('cd') or document.text.startswith('mkdir')) and os.path.isfile(file):
                continue
            if os.path.isdir(file):
                dirs_.append(file)
            else:
                files_.append(file)

        for d in dirs_:
            sep = os.path.sep
            yield Completion(d + sep, start_position=-start_position,
                             style='class:path-completion',
                             selected_style='class:path-completion-selected')

        for f in files_:
            yield Completion(f, start_position=-start_position,
                             style='class:file-completion',
                             selected_style='class:file-completion-selected')


class HistoryCompleter(WordCompleter):
    def get_completions(self, document, complete_event):
        completions = super().get_completions(document, complete_event)
        for completion in completions:
            completion.style = 'class:history-completion'
            completion.selected_style = 'class:history-completion-selected'
            yield completion


class MergedCompleter(Completer):
    def __init__(self, path_completer, history_completer):
        self.path_completer = path_completer
        self.history_completer = history_completer

    def get_completions(self, document, complete_event):
        text = document.text.lstrip()

        if text.startswith('cd ') or\
            text.startswith('ls ') or\
            text.startswith('touch ') or\
            text.startswith('cat ') or\
            text.startswith('mkdir ') or\
            text.startswith('open ') or\
            text.startswith('rm ') or\
            text.startswith('git ') or\
            text.startswith('*') or\
            text.startswith(r'.\\') or\
            text.startswith(r'~\\') or\
            text.startswith(r'\\') or\
            text.startswith('.\\') or\
            text.startswith('~\\') or\
            text.startswith('\\') or\
            text.startswith('./') or\
            text.startswith('~/') or\
            text.startswith('/'):
            yield from self.path_completer.get_completions(document, complete_event)
            yield from self.history_completer.get_completions(document, complete_event)
        else:
            yield from self.history_completer.get_completions(document, complete_event)
            yield from self.path_completer.get_completions(document, complete_event)


# Create custom keybindings
bindings = KeyBindings()


def get_conda_env():
    return os.environ.get('CONDA_DEFAULT_ENV')


# bind to 'Ctrl' + 'Space'
@bindings.add(Keys.ControlSpace)
def _(event):
    current_user_input = event.current_buffer.document.text
    func = Function(SHELL_CONTEXT)

    bottom_toolbar = HTML(' <b>[f]</b> Print "f" <b>[x]</b> Abort.')

    # Create custom key bindings first.
    kb = KeyBindings()

    cancel = [False]
    @kb.add('f')
    def _(event):
        print('You pressed `f`.')

    @kb.add('x')
    def _(event):
        " Send Abort (control-c) signal. "
        cancel[0] = True
        os.kill(os.getpid(), signal.SIGINT)

    # Use `patch_stdout`, to make sure that prints go above the
    # application.
    with patch_stdout():
        with ProgressBar(key_bindings=kb, bottom_toolbar=bottom_toolbar) as pb:
            # TODO: hack to simulate progress bar of indeterminate length of an synchronous function
            for i in pb(range(100)):
                if i > 50 and i < 70:
                    time.sleep(.01)

                if i == 60:
                    res = func(current_user_input) # hack to see progress bar

                # Stop when the cancel flag has been set.
                if cancel[0]:
                    break

    with ConsoleStyle('code') as console:
        console.print(res)


@bindings.add(Keys.PageUp)
def _(event):
    # Moving up for 5 lines
    for _ in range(5):
        event.current_buffer.auto_up()


@bindings.add(Keys.PageDown)
def _(event):
    # Moving down for 5 lines
    for _ in range(5):
        event.current_buffer.auto_down()


class FileHistory(History):
    '''
    :class:`.History` class that stores all strings in a file.
    '''

    def __init__(self, filename: str) -> None:
        self.filename = filename
        super().__init__()

    def load_history_strings(self) -> Iterable[str]:
        lines: list[str] = []

        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                lines = f.readlines()
                # Remove comments and empty lines.
                lines = [line for line in lines if line.strip() and not line.startswith("#")]
                # Remove whitespace at the end and \n.
                lines = [line.rstrip() for line in lines]
                # only keep unique lines
                lines = list(dict.fromkeys(lines))

        # Reverse the order, because newest items have to go first.
        return reversed(lines)

    def store_string(self, string: str) -> None:
        # Save to file.
        with open(self.filename, "ab") as f:

            def write(t: str) -> None:
                f.write(t.encode("utf-8"))

            for line in string.split("\n"):
                write("%s\n" % line)


# Defining commands history
def load_history(home_path=os.path.expanduser('~'), history_file='.bash_history'):
    history_file_path = os.path.join(home_path, history_file)
    history = FileHistory(history_file_path)
    return history, list(history.load_history_strings())


# Function to check if current directory is a git directory
def get_git_branch():
    try:
        git_process = subprocess.Popen(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = git_process.communicate()
        if git_process.returncode == 0:
            return stdout.strip().decode('utf-8')
    except FileNotFoundError:
        pass
    return None


# query language model
def query_language_model(query: str, from_shell=True, res=None, *args, **kwargs):
    global stateful_conversation
    home_path = os.path.expanduser('~')
    symai_path = os.path.join(home_path, '.symai', '.conversation_state')
    if (query.startswith('!"') or query.startswith("!'") or query.startswith('!`')):
        os.makedirs(os.path.dirname(symai_path), exist_ok=True)
        Conversation.save_conversation_state(Conversation(auto_print=False), symai_path)
        stateful_conversation = Conversation.load_conversation_state(symai_path)
    elif (query.startswith('."') or query.startswith(".'") or query.startswith('.`')) and stateful_conversation is None:
        if not os.path.exists(symai_path):
            os.makedirs(os.path.dirname(symai_path), exist_ok=True)
            Conversation.save_conversation_state(Conversation(auto_print=False), symai_path)
        stateful_conversation = Conversation.load_conversation_state(symai_path)

    if '|' in query and from_shell:
        cmds = query.split('|')
        query = cmds[0]
        files = ' '.join(cmds[1:]).split(' ')
        if query.startswith('."') or query.startswith(".'") or query.startswith('.`') or\
            query.startswith('!"') or query.startswith("!'") or query.startswith('!`'):
            func = stateful_conversation
            for fl in files:
                func.store_file(fl)
        else:
            func = Conversation(file_link=files, auto_print=False)
    else:
        if query.startswith('."') or query.startswith(".'") or query.startswith('.`') or\
            query.startswith('!"') or query.startswith("!'") or query.startswith('!`'):
            func = stateful_conversation
        else:
            func = Function(SHELL_CONTEXT)

    with Loader(desc="Inference ...", end=""):
        if res is not None:
            query = f'{str(res)}\n' @ Symbol(query)
        msg = func(query, *args, **kwargs)

    return msg


def retrieval_augmented_indexing(query: str, *args, **kwargs):
    global stateful_conversation
    sep = os.path.sep
    path = query
    if path.startswith('git@') or path.startswith('git:'):
        repo_path = os.path.join(os.path.expanduser('~'), '.symai', 'temp')
        cloner = RepositoryCloner(repo_path=repo_path)
        url = path[4:]
        if 'http' not in url:
            url = 'https://' + url
        url = url.replace('.com:', '.com/')
        # if ends with '.git' then remove it
        if url.endswith('.git'):
            url = url[:-4]
        path = cloner(url)

    merger = FileMerger()
    file = merger(path)
    arxiv = ArxivPdfParser()
    pdf_file = arxiv(file)
    if pdf_file is not None:
        file = file @'\n'@ pdf_file

    index_name = path.split(sep)[-1]
    print(f'Indexing {index_name} ...')
    # creates index if not exists
    DocumentRetriever(file=file, index_name=index_name, overwrite=False)

    home_path = os.path.expanduser('~')
    symai_path = os.path.join(home_path, '.symai', '.conversation_state')
    os.makedirs(os.path.dirname(symai_path), exist_ok=True)
    Conversation.save_conversation_state(Conversation(auto_print=False, index_name=index_name), symai_path)
    stateful_conversation = Conversation.load_conversation_state(symai_path)
    message = f'Repository {url} cloned and ' if query.startswith('git@') or query.startswith('git:') else f'Directory {path} '
    msg = f'{message}successfully indexed: {index_name}'
    return msg


# run shell command
def run_shell_command(cmd: str, prev=None, auto_query_on_error: bool=False, stdout=None, stderr=None):
    if prev is not None:
        cmd = prev + ' && ' + cmd
    # Execute the command
    try:
        shell_true = not os.name == 'nt'
        stdout = subprocess.PIPE if auto_query_on_error else stdout
        stderr = subprocess.PIPE if auto_query_on_error else stderr
        res = subprocess.run(cmd,
                             shell=shell_true,
                             stdout=stdout,
                             stderr=stderr)
        if res and stdout and res.stdout:
            print(res.stdout.decode('utf-8'))
        if res and stderr and res.stderr:
            print(res.stderr.decode('utf-8'))
    except FileNotFoundError as e:
        print(e)
        return
    except PermissionError as e:
        print(e)
        return

    # all good
    if res.returncode == 0:
        pass
    # If command not found, then try to query language model
    else:
        msg = Symbol(cmd) @ f'\n{str(res)}'
        if 'command not found' in str(res) or 'not recognized as an internal or external command' in str(res):
            print(res.stderr.decode('utf-8'))
        else:
            stderr = res.stderr
            if stderr and auto_query_on_error:
                rsp = stderr.decode('utf-8')
                print(rsp)
                msg = msg @ f"\n{rsp}"
                if 'usage:' in rsp:
                    try:
                        cmd = cmd.split('usage: ')[-1].split(' ')[0]
                        # get man page result for command
                        shell_true = not os.name == 'nt'
                        res = subprocess.run('man -P cat %s' % cmd,
                                             shell=shell_true,
                                             stdout=subprocess.PIPE)
                        stdout = res.stdout
                        if stdout:
                            rsp = stdout.decode('utf-8')[:500]
                            msg = msg @ f"\n{rsp}"
                    except Exception:
                        pass

                query_language_model(msg, from_shell=False)
            else:
                stdout = res.stdout
                if stdout:
                    rsp = stderr.decode('utf-8')
                    print(rsp)


def is_llm_request(cmd: str):
    return cmd.startswith('"') or cmd.startswith('."') or cmd.startswith('!"') or\
            cmd.startswith("'") or cmd.startswith(".'") or cmd.startswith("!'") or\
            cmd.startswith('`') or cmd.startswith('.`') or cmd.startswith('!`')


def process_command(cmd: str, res=None, auto_query_on_error: bool=False):
    sep = os.path.sep
    # check if commands are chained
    if '&&' in cmd:
        cmds = cmd.split('&&')
        for c in cmds:
            res = process_command(c.strip(), res=res)
        return res

    if not is_llm_request(cmd) and '|' in cmd:
        return run_shell_command(cmd, prev=res, auto_query_on_error=True, stderr=subprocess.PIPE)

    # check command type
    if  is_llm_request(cmd) or '...' in cmd:
        return query_language_model(cmd, res=res)

    elif cmd.startswith('*'):
        cmd = cmd[1:]
        return retrieval_augmented_indexing(cmd)

    elif cmd.startswith('cd'):
        try:
            # replace ~ with home directory
            cmd = cmd.replace('~', os.path.expanduser('~'))
            # Change directory
            path = ' '.join(cmd.split(' ')[1:])
            if path.endswith(sep):
                path = path[:-1]
            return os.chdir(path)
        except FileNotFoundError as e:
            print(e)
            return e
        except PermissionError as e:
            print(e)
            return e

    elif os.path.isdir(cmd):
        try:
            # replace ~ with home directory
            cmd = cmd.replace('~', os.path.expanduser('~'))
            # Change directory
            os.chdir(cmd)
        except FileNotFoundError as e:
            print(e)
            return e
        except PermissionError as e:
            print(e)
            return e

    elif cmd.startswith('ll'):
        if os.name == 'nt':
            return run_shell_command('dir', prev=res)
        else:
            return run_shell_command('ls -l', prev=res)

    else:
        return run_shell_command(cmd, prev=res, auto_query_on_error=auto_query_on_error)


# Function to listen for user input and execute commands
def listen(session: PromptSession, word_comp: WordCompleter, auto_query_on_error: bool=False):
    with patch_stdout():
        while True:
            try:
                git_branch = get_git_branch()
                conda_env = get_conda_env()
                # get directory from the shell
                cur_working_dir = os.getcwd()
                sep = os.path.sep
                if cur_working_dir.startswith(sep):
                    cur_working_dir = cur_working_dir.replace(os.path.expanduser('~'), '~')
                paths = cur_working_dir.split(sep)
                prev_paths = sep.join(paths[:-1])
                last_path = paths[-1]

                # Format the prompt
                if len(paths) > 1:
                    cur_working_dir = f'{prev_paths}{sep}<b>{last_path}</b>'
                else:
                    cur_working_dir = f'<b>{last_path}</b>'

                if git_branch:
                    prompt = HTML(f"<ansiblue>{cur_working_dir}</ansiblue><ansiwhite> on git:[</ansiwhite><ansigreen>{git_branch}</ansigreen><ansiwhite>]</ansiwhite> <ansiwhite>conda:[</ansiwhite><ansimagenta>{conda_env}</ansimagenta><ansiwhite>]</ansiwhite> <ansicyan><b>symsh:</b> ❯</ansicyan> ")
                else:
                    prompt = HTML(f"<ansiblue>{cur_working_dir}</ansiblue> <ansiwhite>conda:[</ansiwhite><ansimagenta>{conda_env}</ansimagenta><ansiwhite>]</ansiwhite> <ansicyan><b>symsh:</b> ❯</ansicyan> ")

                # Read user input
                cmd = session.prompt(prompt, lexer=PygmentsLexer(BashLexer))
                if cmd.strip() == '':
                    continue

                if cmd == 'quit' or cmd == 'exit' or cmd == 'q':
                    if stateful_conversation is not None:
                        home_path = os.path.expanduser('~')
                        symai_path = os.path.join(home_path, '.symai', '.conversation_state')
                        Conversation.save_conversation_state(stateful_conversation, symai_path)
                    print('Goodbye!')
                    os._exit(0)
                else:
                    msg = process_command(cmd, auto_query_on_error=auto_query_on_error)
                    if msg is not None:
                        with ConsoleStyle('code') as console:
                            console.print(msg)

                # Append the command to the word completer list
                word_comp.words.append(cmd)

            except KeyboardInterrupt:
                print()
                pass

            except Exception as e:
                print(e)
                pass


def create_session(history, merged_completer):
    # Load style
    style = Style.from_dict(SYMSH_CONFIG)

    # Session for the auto-completion
    session = PromptSession(history=history,
                            completer=merged_completer,
                            complete_style=CompleteStyle.MULTI_COLUMN,
                            reserve_space_for_menu=5,
                            style=style,
                            key_bindings=bindings)

    return session


def create_completer():
    # Load history
    history, history_strings = load_history()

    # Create your specific completers
    word_comp = HistoryCompleter(history_strings, ignore_case=True, sentence=True)
    custom_completer = PathCompleter()

    # Merge completers
    merged_completer = MergedCompleter(custom_completer, word_comp)
    return history, word_comp, merged_completer


def run(auto_query_on_error=False):
    history, word_comp, merged_completer = create_completer()
    session = create_session(history, merged_completer)
    listen(session, word_comp, auto_query_on_error)


if __name__ == '__main__':
    run()
