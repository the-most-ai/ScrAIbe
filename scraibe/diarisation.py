"""
Diarisation Class
------------------

This class serves as the heart of the speaker diarization system, responsible for identifying
and segmenting individual speakers from a given audio file. It leverages a pretrained model
from pyannote.audio, providing an accessible interface for audio processing tasks such as
speaker separation, and timestamping.

By encapsulating the complexities of the underlying model, it allows for straightforward
integration into various applications, ranging from transcription services to voice assistants.

Available Classes:
- Diariser: Main class for performing speaker diarization. 
            Includes methods for loading models, processing audio files,
            and formatting the diarization output.

Constants:
- TOKEN_PATH (str): Path to the Pyannote token.
- PYANNOTE_DEFAULT_PATH (str): Default path to Pyannote models.
- PYANNOTE_DEFAULT_CONFIG (str): Default configuration for Pyannote models.

Usage:
    from .diarisation import Diariser

    model = Diariser.load_model(model="path/to/model/config.yaml")
    diarisation_output = model.diarization("path/to/audiofile.wav")
"""

import warnings
import os
import yaml
from pathlib import Path
from typing import TypeVar, Union

from pyannote.audio import Pipeline
from pyannote.audio.pipelines.speaker_diarization import SpeakerDiarization
from torch import Tensor
from torch import device as torch_device

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from .misc import PYANNOTE_DEFAULT_PATH, PYANNOTE_DEFAULT_CONFIG, SCRAIBE_TORCH_DEVICE
Annotation = TypeVar('Annotation')

TOKEN_PATH = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), '.pyannotetoken')


class Diariser:
    """
    Handles the diarization process of an audio file using a pretrained model
    from pyannote.audio. Diarization is the task of determining "who spoke when."

    Args:
        model: The pretrained model to use for diarization.
    """

    def __init__(self, model) -> None:

        self.model = model

    def diarization(self, audiofile: Union[str, Tensor, dict],
                    *args, **kwargs) -> Annotation:
        """
        Perform speaker diarization on the provided audio file, 
        effectively separating different speakers
        and providing a timestamp for each segment.

        Args:
            audiofile: The path to the audio file or a torch.Tensor
                        containing the audio data.
            args: Additional arguments for the diarization model.
            kwargs: Additional keyword arguments for the diarization model.

        Returns:
            dict: A dictionary containing speaker names,
                    segments, and other information related
                    to the diarization process.
        """
        kwargs = self._get_diarisation_kwargs(**kwargs)

        diarization = self.model(audiofile, *args, **kwargs)

        out = self.format_diarization_output(diarization)

        return out

    @staticmethod
    def format_diarization_output(dia: Annotation) -> dict:
        """
        Formats the raw diarization output into a more usable structure for this project.

        Args:
            dia: Raw diarization output.

        Returns:
            dict: A structured representation of the diarization, with speaker names
                  as keys and a list of tuples representing segments as values.
        """

        dia_list = list(dia.itertracks(yield_label=True))
        diarization_output = {"speakers": [], "segments": []}

        normalized_output = []
        index_start_speaker = 0
        index_end_speaker = 0
        current_speaker = str()

        ###
        # Sometimes two consecutive speakers are the same
        # This loop removes these duplicates
        ###

        if len(dia_list) == 1:
            normalized_output.append([0, 0, dia_list[0][2]])
        else:

            for i, (_, _, speaker) in enumerate(dia_list):

                if i == 0:
                    current_speaker = speaker

                if speaker != current_speaker:

                    index_end_speaker = i - 1

                    normalized_output.append([index_start_speaker,
                                              index_end_speaker,
                                              current_speaker])

                    index_start_speaker = i
                    current_speaker = speaker

                if i == len(dia_list) - 1:

                    index_end_speaker = i

                    normalized_output.append([index_start_speaker,
                                              index_end_speaker,
                                              current_speaker])

        for outp in normalized_output:
            start = dia_list[outp[0]][0].start
            end = dia_list[outp[1]][0].end

            diarization_output["segments"].append([start, end])
            diarization_output["speakers"].append(outp[2])
        return diarization_output

    @staticmethod
    def _get_token():
        """
        Retrieves the Huggingface token from a local file. This token is required
        for accessing certain online resources.

        Raises:
            ValueError: If the token is not found.

        Returns:
            str: The Huggingface token.
        """

        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'r', encoding="utf-8") as file:
                token = file.read()
        else:
            raise ValueError('No token found.'
                             'Please create a token at https://huggingface.co/settings/token'
                             f'and save it in a file called {TOKEN_PATH}')
        return token

    @staticmethod
    def _save_token(token):
        """
        Saves the provided Huggingface token to a local file. This facilitates future
        access to online resources without needing to repeatedly authenticate.

        Args:
            token: The Huggingface token to save.
        """
        with open(TOKEN_PATH, 'w', encoding="utf-8") as file:
            file.write(token)

    @classmethod
    def load_model(cls,
                   model: str = PYANNOTE_DEFAULT_CONFIG,
                   use_auth_token: str = None,
                   cache_token: bool = False,
                   cache_dir: Union[Path, str] = PYANNOTE_DEFAULT_PATH,
                   hparams_file: Union[str, Path] = None,
                   device: str = SCRAIBE_TORCH_DEVICE,
                   ) -> Pipeline:
        """
        Loads a pretrained model from pyannote.audio, 
        either from a local cache or some online repository.

        Args:
            model: Path or identifier for the pyannote model.
                default: '/home/[user]/.cache/torch/models/pyannote/config.yaml'
                or one of 'jaikinator/scraibe', 'pyannote/speaker-diarization-3.1'
            token: Optional HUGGINGFACE_TOKEN for authenticated access.
            cache_token: Whether to cache the token locally for future use.
            cache_dir: Directory for caching models.
            hparams_file: Path to a YAML file containing hyperparameters.
            device: Device to load the model on.
            args: Additional arguments only to avoid errors.
            kwargs: Additional keyword arguments only to avoid errors.

        Returns:
            Pipeline: A pyannote.audio Pipeline object, encapsulating the loaded model.
        """
        if isinstance(model, str) and os.path.exists(model):
            # check if model can be found locally nearby the config file
            with open(model, 'r') as file:
                config = yaml.safe_load(file)

            path_to_model = config['pipeline']['params']['segmentation']

            if not os.path.exists(path_to_model):
                warnings.warn(f"Model not found at {path_to_model}. "
                              "Trying to find it nearby the config file.")

                pwd = model.split("/")[:-1]
                pwd = "/".join(pwd)

                path_to_model = os.path.join(pwd, "pytorch_model.bin")

                if not os.path.exists(path_to_model):
                    warnings.warn(f"Model not found at {path_to_model}. \
                        'Trying to find it nearby .bin files instead.")
                    warnings.warn(
                        'Searching for nearby files in a folder path is '
                        'deprecated and will be removed in future versions.',
                        category=DeprecationWarning)
                    # list elementes with the ending .bin
                    bin_files = [f for f in os.listdir(
                        pwd) if f.endswith(".bin")]
                    if len(bin_files) == 1:
                        path_to_model = os.path.join(pwd, bin_files[0])
                    else:
                        warnings.warn("Found more than one .bin file. "
                                      "or none. Please specify the path to the model "
                                      "or setup a huggingface token.")
                        raise FileNotFoundError

                warnings.warn(
                    f"Found model at {path_to_model} overwriting config file.")

                config['pipeline']['params']['segmentation'] = path_to_model

                with open(model, 'w') as file:
                    yaml.dump(config, file)
        elif isinstance(model, tuple):
            try:
                _model = model[0]
                HfApi().model_info(_model)
                model = _model
                use_auth_token = None
            except RepositoryNotFoundError:
                print(f'{model[0]} not found on Huggingface, \
                      trying {model[1]}')
                _model = model[1]
                HfApi().model_info(_model)
                model = _model
                if cache_token and use_auth_token is not None:
                    cls._save_token(use_auth_token)

                if use_auth_token is None:
                    use_auth_token = cls._get_token()
        else:
            raise FileNotFoundError(
                f'No local model or directory found at {model}.')

        _model = Pipeline.from_pretrained(model,
                                          use_auth_token=use_auth_token,
                                          cache_dir=cache_dir,
                                          hparams_file=hparams_file,)
        if _model is None:
            raise ValueError('Unable to load model either from local cache'
                             'or from huggingface.co models. Please check your token'
                             'or your local model path')

        # torch_device is renamed from torch.device to avoid name conflict
        _model = _model.to(torch_device(device))

        return cls(_model)

    @staticmethod
    def _get_diarisation_kwargs(**kwargs) -> dict:
        """
        Validates and extracts the keyword arguments for the pyannote diarization model.

        Ensures that the provided keyword arguments match the expected parameters,
        filtering out any invalid or unnecessary arguments.

        Returns:
            dict: A dictionary containing the validated keyword arguments.
        """
        _possible_kwargs = SpeakerDiarization.apply.__code__.co_varnames

        diarisation_kwargs = {k: v for k,
                              v in kwargs.items() if k in _possible_kwargs}

        return diarisation_kwargs

    def __repr__(self):
        return f"Diarisation(model={self.model})"
