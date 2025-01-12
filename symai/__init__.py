import json
import logging
import os
from pathlib import Path

# do not remove - hides the libraries' debug messages
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("tika").setLevel(logging.ERROR)


SYMAI_VERSION = "0.2.56"
__version__   = SYMAI_VERSION
__root_dir__  = Path.home() / '.symai'


def _start_symai():
    global _symai_config_
    global _symsh_config_

    # CREATE THE SYMAI FOLDER IF IT DOES NOT EXIST YET
    # *==============================================================================================================*
    if not os.path.exists(__root_dir__):
        os.makedirs(__root_dir__)

    # CREATE THE SHELL CONFIGURATION FILE IF IT DOES NOT EXIST YET
    # *==============================================================================================================*
    _symsh_config_path_ = __root_dir__ / 'symsh.config.json'
    if not os.path.exists(_symsh_config_path_):
        with open(_symsh_config_path_, "w") as f:
            json.dump({
                "completion-menu.completion.current": "bg:#323232 #212121",
                "completion-menu.completion":         "bg:#800080 #212121",
                "scrollbar.background":               "bg:#222222",
                "scrollbar.button":                   "bg:#776677",
                "history-completion":                 "bg:#212121 #f5f5f5",
                "path-completion":                    "bg:#800080 #f5f5f5",
                "file-completion":                    "bg:#9040b2 #f5f5f5",
                "history-completion-selected":        "bg:#efefef #b3d7ff",
                "path-completion-selected":           "bg:#efefef #b3d7ff",
                "file-completion-selected":           "bg:#efefef #b3d7ff",
            }, f, indent=4)

    # CHECK IF THE USER HAS A CONFIGURATION FILE IN THE CURRENT WORKING DIRECTORY (DEBUGGING MODE)
    # *==============================================================================================================*
    if os.path.exists(Path.cwd() / 'symai.config.json'):
        logging.debug('Using the configuration file in the current working directory.')
        _symai_config_path_ = Path.cwd() / 'symai.config.json'

    else:
        # CREATE THE CONFIGURATION FILE IF IT DOES NOT EXIST YET WITH THE DEFAULT VALUES
        # *==========================================================================================================*
        _symai_config_path_ = __root_dir__ / 'symai.config.json'

        if not os.path.exists(_symai_config_path_):
            with open(_symai_config_path_, 'w') as f:
                json.dump({
                    "NEUROSYMBOLIC_ENGINE_API_KEY":   "",
                    "NEUROSYMBOLIC_ENGINE_MODEL":     "text-davinci-003",
                    "SYMBOLIC_ENGINE_API_KEY":        "",
                    "SYMBOLIC_ENGINE":                "wolframalpha",
                    "EMBEDDING_ENGINE_API_KEY":       "",
                    "EMBEDDING_ENGINE_MODEL":         "text-embedding-ada-002",
                    "IMAGERENDERING_ENGINE_API_KEY":  "",
                    "VISION_ENGINE_MODEL":            "openai/clip-vit-base-patch32",
                    "SEARCH_ENGINE_API_KEY":          "",
                    "SEARCH_ENGINE_MODEL":            "google",
                    "OCR_ENGINE_API_KEY":             "",
                    "SPEECH_ENGINE_MODEL":            "base",
                    "INDEXING_ENGINE_API_KEY":        "",
                    "INDEXING_ENGINE_ENVIRONMENT":    "us-west1-gcp",
                    "CAPTION_ENGINE_MODEL":           "base_coco"
                }, f, indent=4)

        # LOAD THE CONFIGURATION FILE
        # *==========================================================================================================*
        with open(_symai_config_path_, 'r') as f:
            _symai_config_ = json.load(f)
        _tmp_symai_config_ = _symai_config_.copy()

        # LOAD THE ENVIRONMENT VARIABLES
        # *==========================================================================================================*
        _openai_api_key_                = os.environ.get('OPENAI_API_KEY', None)
        _neurosymbolic_engine_api_key_  = os.environ.get('NEUROSYMBOLIC_ENGINE_API_KEY', None)
        _neurosymbolic_engine_model_    = os.environ.get('NEUROSYMBOLIC_ENGINE_MODEL', None)
        _symbolic_engine_api_key_       = os.environ.get('SYMBOLIC_ENGINE_API_KEY', None)
        _embedding_engine_api_key_      = os.environ.get('EMBEDDING_ENGINE_API_KEY', None)
        _embedding_engine_model_        = os.environ.get('EMBEDDING_ENGINE_MODEL', None)
        _imagerendering_engine_api_key_ = os.environ.get('IMAGERENDERING_ENGINE_API_KEY', None)
        _vision_engine_model_           = os.environ.get('VISION_ENGINE_MODEL', None)
        _search_engine_api_key_         = os.environ.get('SEARCH_ENGINE_API_KEY', None)
        _search_engine_model_           = os.environ.get('SEARCH_ENGINE_MODEL', None)
        _ocr_engine_api_key_            = os.environ.get('OCR_ENGINE_API_KEY', None)
        _speech_engine_model_           = os.environ.get('SPEECH_ENGINE_MODEL', None)
        _indexing_engine_api_key_       = os.environ.get('INDEXING_ENGINE_API_KEY', None)
        _indexing_engine_environment_   = os.environ.get('INDEXING_ENGINE_ENVIRONMENT', None)
        _caption_engine_environment_    = os.environ.get('CAPTION_ENGINE_ENVIRONMENT', None)

        # SET/UPDATE THE API KEYS
        # *==========================================================================================================*
        if _neurosymbolic_engine_api_key_:  _symai_config_['NEUROSYMBOLIC_ENGINE_API_KEY']  = _neurosymbolic_engine_api_key_
        if _symbolic_engine_api_key_:       _symai_config_['SYMBOLIC_ENGINE_API_KEY']       = _symbolic_engine_api_key_
        if _embedding_engine_api_key_:      _symai_config_['EMBEDDING_ENGINE_API_KEY']      = _embedding_engine_api_key_
        if _imagerendering_engine_api_key_: _symai_config_['IMAGERENDERING_ENGINE_API_KEY'] = _imagerendering_engine_api_key_

        # USE ENVIRONMENT VARIABLES IF THE USER DID NOT SET THE API KEYS
        # *==========================================================================================================*
        if _openai_api_key_ and not _neurosymbolic_engine_api_key_:  _symai_config_['NEUROSYMBOLIC_ENGINE_API_KEY']  = _openai_api_key_
        if _openai_api_key_ and not _embedding_engine_api_key_:      _symai_config_['EMBEDDING_ENGINE_API_KEY']      = _openai_api_key_
        if _openai_api_key_ and not _imagerendering_engine_api_key_: _symai_config_['IMAGERENDERING_ENGINE_API_KEY'] = _openai_api_key_

        # OPTIONAL MODULES
        # *==========================================================================================================*
        if _neurosymbolic_engine_model_:  _symai_config_['NEUROSYMBOLIC_ENGINE_MODEL']  = _neurosymbolic_engine_model_
        if _embedding_engine_model_:      _symai_config_['EMBEDDING_ENGINE_MODEL']      = _embedding_engine_model_
        if _vision_engine_model_:         _symai_config_['VISION_ENGINE_MODEL']         = _vision_engine_model_
        if _search_engine_api_key_:       _symai_config_['SEARCH_ENGINE_API_KEY']       = _search_engine_api_key_
        if _search_engine_model_:         _symai_config_['SEARCH_ENGINE_MODEL']         = _search_engine_model_
        if _ocr_engine_api_key_:          _symai_config_['OCR_ENGINE_API_KEY']          = _ocr_engine_api_key_
        if _speech_engine_model_:         _symai_config_['SPEECH_ENGINE_MODEL']         = _speech_engine_model_
        if _indexing_engine_api_key_:     _symai_config_['INDEXING_ENGINE_API_KEY']     = _indexing_engine_api_key_
        if _indexing_engine_environment_: _symai_config_['INDEXING_ENGINE_ENVIRONMENT'] = _indexing_engine_environment_
        if _caption_engine_environment_:  _symai_config_['CAPTION_ENGINE_ENVIRONMENT']  = _caption_engine_environment_

        # VERIFY IF THE CONFIGURATION FILE HAS CHANGED AND UPDATE IT
        # *==========================================================================================================*
        _updated_key_ = {k: not _tmp_symai_config_[k] == _symai_config_[k] for k in _tmp_symai_config_.keys()}
        _has_changed_ = any(_updated_key_.values())

        if _has_changed_:
            # update the symai.config.json file
            with open(_symai_config_path_, 'w') as f:
                json.dump(_symai_config_, f, indent=4)

    # CHECK IF MANADATORY API KEYS ARE SET
    # *==============================================================================================================*
    with open(_symai_config_path_, 'r') as f:
        _symai_config_ = json.load(f)

    # LOAD THE SHELL CONFIGURATION FILE
    # *==========================================================================================================*
    with open(_symsh_config_path_, 'r') as f:
        _symsh_config_ = json.load(f)

    if 'custom' not in _symai_config_['NEUROSYMBOLIC_ENGINE_MODEL'].lower() and \
                      (_symai_config_['NEUROSYMBOLIC_ENGINE_API_KEY'] is None or len(_symai_config_['NEUROSYMBOLIC_ENGINE_API_KEY']) == 0):

        logging.warn('The mandatory neuro-symbolic engine is not initialized. Please get a key from https://beta.openai.com/account/api-keys and set either a general environment variable OPENAI_API_KEY or a module specific environment variable NEUROSYMBOLIC_ENGINE_API_KEY.')

    import symai.backend.settings as settings
    settings.SYMAI_CONFIG = _symai_config_
    settings.SYMSH_CONFIG = _symsh_config_


_start_symai()


from .backend.base import Engine
from .chat import ChatBot, SymbiaChat
from .components import *
from .constraints import *
from .core import *
from .exceptions import *
from .formatter import *
from .imports import *
from .interfaces import *
from .memory import *
from .post_processors import *
from .pre_processors import *
from .prompts import Prompt
from .shell import Shell
from .strategy import *
from .symbol import *
from .utils import parallel
