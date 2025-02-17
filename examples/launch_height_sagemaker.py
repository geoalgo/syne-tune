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
"""
Example showing how to run on Sagemaker with a Sagemaker Framework.
"""
import logging
import os
from pathlib import Path

from sagemaker.pytorch import PyTorch

from syne_tune import Tuner, StoppingCriterion
from syne_tune.backend import SageMakerBackend
from syne_tune.backend.sagemaker_backend.sagemaker_utils import (
    get_execution_role,
    default_sagemaker_session,
)
from syne_tune.config_space import randint
from examples.training_scripts.height_example.train_height import (
    METRIC_ATTR,
    METRIC_MODE,
    MAX_RESOURCE_ATTR,
)
from syne_tune.optimizer.baselines import RandomSearch
from syne_tune.remote.estimators import (
    PYTORCH_LATEST_FRAMEWORK,
    PYTORCH_LATEST_PY_VERSION,
    DEFAULT_CPU_INSTANCE_SMALL,
)

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    random_seed = 31415927
    max_steps = 100
    n_workers = 4
    max_wallclock_time = 5 * 60

    config_space = {
        MAX_RESOURCE_ATTR: max_steps,
        "width": randint(0, 20),
        "height": randint(-100, 100),
    }
    entry_point = (
        Path(__file__).parent
        / "training_scripts"
        / "height_example"
        / "train_height.py"
    )

    # Random search without stopping
    scheduler = RandomSearch(
        config_space, mode=METRIC_MODE, metric=METRIC_ATTR, random_seed=random_seed
    )
    if "AWS_DEFAULT_REGION" not in os.environ:
        os.environ["AWS_DEFAULT_REGION"] = "us-west-2"

    trial_backend = SageMakerBackend(
        # we tune a PyTorch Framework from Sagemaker
        sm_estimator=PyTorch(
            instance_type=DEFAULT_CPU_INSTANCE_SMALL,
            instance_count=1,
            framework_version=PYTORCH_LATEST_FRAMEWORK,
            py_version=PYTORCH_LATEST_PY_VERSION,
            entry_point=str(entry_point),
            role=get_execution_role(),
            max_run=10 * 60,
            sagemaker_session=default_sagemaker_session(),
            disable_profiler=True,
            debugger_hook_config=False,
        ),
        # names of metrics to track. Each metric will be detected by Sagemaker if it is written in the
        # following form: "[RMSE]: 1.2", see in train_main_example how metrics are logged for an example
        metrics_names=[METRIC_ATTR],
    )

    stop_criterion = StoppingCriterion(max_wallclock_time=max_wallclock_time)
    tuner = Tuner(
        trial_backend=trial_backend,
        scheduler=scheduler,
        stop_criterion=stop_criterion,
        n_workers=n_workers,
        sleep_time=5.0,
        tuner_name="hpo-hyperband",
    )

    tuner.run()
