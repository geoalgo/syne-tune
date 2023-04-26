# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.
import logging
import os
import re
import string
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import sagemaker
from typing import Optional
from typing import Optional, List, Union
from time import perf_counter
from contextlib import contextmanager

from syne_tune.constants import SYNE_TUNE_DEFAULT_FOLDER, SYNE_TUNE_ENV_FOLDER
from syne_tune.try_import import try_import_aws_message

try:
    import sagemaker
except ImportError:
    print(try_import_aws_message())


class RegularCallback:
    """
    Allows to call the callback function at most once every `call_seconds_frequency` seconds.

    :param callback: `TunerCallback` object
    :param call_seconds_frequency: Wait time between subsequent calls
    """

    def __init__(self, callback: callable, call_seconds_frequency: float):
        self.time_last_recent_call = datetime.now()
        self.frequency = call_seconds_frequency
        self.callback = callback

    def __call__(self, *args, **kwargs):
        seconds_since_last_call = (datetime.now() - self.time_last_recent_call).seconds
        if seconds_since_last_call > self.frequency:
            self.time_last_recent_call = datetime.now()
            self.callback(*args, **kwargs)


def experiment_path(
    tuner_name: Optional[str] = None, local_path: Optional[str] = None
) -> Path:
    f"""
    Return the path of an experiment which is used both by the Tuner and to
    collect results of experiments.

    :param tuner_name: Name of a tuning experiment
    :param local_path: Local path where results should be saved when running
        locally outside of SageMaker. If not specified, then the environment
        variable `"SYNETUNE_FOLDER"` is used if defined otherwise `~/syne-tune/`
        is used. Defining the enviroment variable `"SYNETUNE_FOLDER"` allows to
        override the default path.
    :return: Path where to write logs and results for Syne Tune tuner. On
        SageMaker, results are written to "/opt/ml/checkpoints/" so that files
        are persisted continuously to S3 by SageMaker.
    """
    is_sagemaker = "SM_MODEL_DIR" in os.environ
    if is_sagemaker:
        # if SM_MODEL_DIR is present in the environment variable, this means that we are running on Sagemaker
        # we use this path to store results as it is persisted by Sagemaker.
        result_path = Path("/opt/ml/checkpoints")
    else:
        # means we are running on a local machine, we store results in a local path
        if local_path is None:
            if SYNE_TUNE_ENV_FOLDER in os.environ:
                result_path = Path(os.environ[SYNE_TUNE_ENV_FOLDER]).expanduser()
            else:
                result_path = Path(f"~/{SYNE_TUNE_DEFAULT_FOLDER}").expanduser()
        else:
            result_path = Path(local_path)
    if tuner_name is not None:
        result_path = result_path / tuner_name
    return result_path


def s3_experiment_path(
    s3_bucket: Optional[str] = None,
    experiment_name: Optional[str] = None,
    tuner_name: Optional[str] = None,
) -> str:
    """Returns S3 path for storing results and checkpoints.

    :param s3_bucket: If not given, the default bucket for the SageMaker
        session is used
    :param experiment_name: If given, this is used as first directory
    :param tuner_name: If given, this is used as second directory
    :return: S3 path, ending on "/"
    """
    if s3_bucket is None:
        s3_bucket = sagemaker.Session().default_bucket()
    s3_path = f"s3://{s3_bucket}/{SYNE_TUNE_DEFAULT_FOLDER}/"
    for part in (experiment_name, tuner_name):
        if part is not None:
            s3_path += part + "/"
    return s3_path


def check_valid_sagemaker_name(name: str):
    assert re.compile("^[a-zA-Z0-9](-*[a-zA-Z0-9]){0,62}$").match(
        name
    ), f"{name} should consists in alpha-digits possibly separated by character -"


def name_from_base(base: Optional[str], default: str, max_length: int = 63) -> str:
    """Append a timestamp to the provided string.

    This function assures that the total length of the resulting string is
    not longer than the specified max length, trimming the input parameter if
    necessary.

    :param base: String used as prefix to generate the unique name
    :param default: String used if `base is None`
    :param max_length: Maximum length for the resulting string (default: 63)
    :return: Input parameter with appended timestamp
    """
    if base is None:
        check_valid_sagemaker_name(default)
        base = default
    else:
        check_valid_sagemaker_name(base)

    moment = time.time()
    moment_ms = repr(moment).split(".")[1][:3]
    timestamp = time.strftime(
        "%Y-%m-%d-%H-%M-%S-{}".format(moment_ms), time.gmtime(moment)
    )
    trimmed_base = base[: max_length - len(timestamp) - 1]
    return "{}-{}".format(trimmed_base, timestamp)


def random_string(length: int) -> str:
    pool = string.ascii_letters + string.digits
    return "".join(random.choice(pool) for _ in range(length))


def repository_root_path() -> Path:
    """
    :return: Returns path including `syne_tune`, `examples`, `benchmarking`
    """
    return Path(__file__).parent.parent


def script_checkpoint_example_path() -> Path:
    """
    :return: Path of checkpoint example
    """
    path = (
        repository_root_path()
        / "examples"
        / "training_scripts"
        / "checkpoint_example"
        / "checkpoint_example.py"
    )
    assert path.exists()
    return path


def script_height_example_path() -> Path:
    """
    :return: Path of train_heigth example
    """
    path = (
        repository_root_path()
        / "examples"
        / "training_scripts"
        / "height_example"
        / "train_height.py"
    )
    assert path.exists()
    return path


@contextmanager
def catchtime(
    name: str, runtime_dict: Optional[Dict[str, float]] = None, verbose: bool = True
) -> float:
    start = perf_counter()
    try:
        if verbose:
            logging.info(f"start: {name}")
        yield lambda: perf_counter() - start
    finally:
        runtime = perf_counter() - start
        if runtime_dict is not None:
            runtime_dict[name] = runtime
        if verbose:
            print(f"Time for {name}: {runtime:.4f} secs")


if __name__ == "__main__":
    import time

    with catchtime("ya"):
        time.sleep(0.2)

    runtimes = {}
    with catchtime("yo", runtimes):
        time.sleep(1)

    with catchtime("yep", runtimes):
        time.sleep(0.1)
    print(runtimes)


def is_increasing(lst: List[Union[float, int]]) -> bool:
    """
    :param lst: List of float or int entries
    :return: Is `lst` strictly increasing?
    """
    return all(x < y for x, y in zip(lst, lst[1:]))


def is_positive_integer(lst: List[int]) -> bool:
    """
    :param lst: List of int entries
    :return: Are all entries of `lst` of type `int` and positive?
    """
    return all(x == int(x) and x >= 1 for x in lst)
