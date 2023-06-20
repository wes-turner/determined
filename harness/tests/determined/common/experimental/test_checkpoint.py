import os

import boto3
import moto
import pytest

from determined.common import api
from determined.common.experimental import checkpoint
from tests.fixtures import api_responses

_MASTER = "http://localhost:8080"


@pytest.fixture
def standard_session() -> api.Session:
    return api.Session(master=_MASTER, user=None, auth=None, cert=None)


@pytest.fixture
def sample_checkpoint(standard_session: api.Session) -> checkpoint.Checkpoint:
    bindings_checkpoint = api_responses.sample_get_checkpoint().checkpoint
    return checkpoint.Checkpoint._from_bindings(bindings_checkpoint, standard_session)


# Typing directive can be removed when https://github.com/getmoto/moto/issues/4944 is resolved.
@moto.mock_s3  # type: ignore
def test_download_can_download_from_s3_directly(
    sample_checkpoint: checkpoint.Checkpoint, tmp_path: os.PathLike
) -> None:
    """Tests one particular code path (of many existing) for downloading a checkpoint.

    There are several options for checkpoint storage (with access keys, overridden URLs, etc.) this
    test chooses a single, simple set of these options.

    As stored on disk, checkpoints have a complex file structure. This test creates a vastly
    simplified checkpoint consisting solely of a metadata.json file and tests that this file is
    downloaded.
    """
    metadata_payload = "{'determined_version': '0.22.2-dev0'}"
    if sample_checkpoint.training is None or sample_checkpoint.training.experiment_config is None:
        raise ValueError(
            "Test depends on an existing experiment_config within the tested checkpoint."
        )
    storage_conf = sample_checkpoint.training.experiment_config["checkpoint_storage"]
    storage_conf.update({"type": "s3", "secret_key": None, "endpoint_url": None, "prefix": None})

    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=storage_conf["bucket"])
    s3_client.put_object(
        Body=bytes(metadata_payload, "utf-8"),
        Bucket=storage_conf["bucket"],
        Key=f"{sample_checkpoint.uuid}/metadata.json",
    )

    sample_checkpoint.download(path=str(tmp_path), mode=checkpoint.DownloadMode.DIRECT)

    downloaded_metadata_path = os.path.join(tmp_path, "metadata.json")
    assert os.path.exists(downloaded_metadata_path)
    with open(downloaded_metadata_path, "r") as f:
        assert f.read() == metadata_payload
