import pytest
import torch
from scraibe import Scraibe, Diariser, Transcriber, Transcript, AudioProcessor
from unittest.mock import MagicMOck, patch


"""
@pytest.fixture
def example_audio_file(tmp_path):
    audio_path = tmp_path 
"""
@pytest.fixture
def create_scraibe_instance():
    return Scraibe()



def test_scraibe_init(create_scraibe_instance):
    model = create_scraibe_instance
    assert isinstance(model.transcriber, Transcriber)
    assert isinstance(model.diariser, Diariser)


def test_scraibe_autotranscribe(create_scraibe_instance, example_audio_file):
    model = create_scraibe_instance
    transcript = example_audio_file
    assert isinstance(transcript, Transcript)

def test_scraibe_diarization(create_scraibe_instance, example_audio_file):
    model = create_scraibe_instance
    diarisation_result = model.diarisation(example_audio_file)
    assert isinstance(diarisation_result, dict)


def test_scraibe_transcribe(create_scraibe_instance, example_audio_file):
    model = create_scraibe_instance
    transcription_result = model.transcribe(example_audio_file)
    assert isinstance(transcription_result, str)


def test_remove_audio_file(create_scraibe_instance, example_audio_file):
    model = create_scraibe_instance
    with pytest.raises(ValueError):
        model.remove_audio_file("non_existing_audio_file")

    model.remove_audio_file(example_audio_file)
    assert not os.path.exists(example_audio_file)      


def test_get_audio_file(create_scraibe_instance, example_audio_file):
    model = create_scraibe_instance
    audio_file = os.path.exist(example_audio_file)
    assert isinstance(audio_file, AudioProcessor)
    assert isinstance(audio_file.waveform, torch.Tensor)
    assert isinstance(audio_file.sr, torch.Tensor)
