# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import unittest

import torch
import torchvision.models as models
from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
    XnnpackQuantizedPartitioner,
)
from executorch.backends.xnnpack.test.tester import Partition, Tester
from executorch.backends.xnnpack.test.tester.tester import Export
from executorch.exir import CaptureConfig
from torchvision.models.mobilenetv2 import MobileNet_V2_Weights


class TestXNNPACKMobileNetV2(unittest.TestCase):
    mv2 = models.mobilenetv2.mobilenet_v2(weights=MobileNet_V2_Weights)
    mv2 = mv2.eval()
    model_inputs = (torch.ones(1, 3, 224, 244),)

    all_operators = {
        "executorch_exir_dialects_edge__ops_aten__native_batch_norm_legit_no_training_default",
        "executorch_exir_dialects_edge__ops_aten_add_Tensor",
        "executorch_exir_dialects_edge__ops_aten_permute_copy_default",
        "executorch_exir_dialects_edge__ops_aten_addmm_default",
        "executorch_exir_dialects_edge__ops_aten_mean_dim",
        "executorch_exir_dialects_edge__ops_aten_hardtanh_default",
        "executorch_exir_dialects_edge__ops_aten_convolution_default",
    }

    def test_mv2_fp32(self):

        (
            Tester(self.mv2, self.model_inputs)
            .export(Export(CaptureConfig(enable_aot=True)))
            .to_edge()
            .check(list(self.all_operators))
            .partition()
            .check(["torch.ops.executorch_call_delegate"])
            .check_not(list(self.all_operators))
            .to_executorch()
            .serialize()
            .run_method()
            .compare_outputs()
        )

    def test_mv2_qs8_pt2e(self):
        # Quantization fuses away batchnorm, so it is no longer in the graph
        ops_after_quantization = self.all_operators - {
            "executorch_exir_dialects_edge__ops_aten__native_batch_norm_legit_no_training_default",
        }

        (
            Tester(self.mv2, self.model_inputs)
            .quantize2()
            .export(Export(CaptureConfig(enable_aot=True)))
            .to_edge()
            .check(list(ops_after_quantization))
            .partition(Partition(partitioner=XnnpackQuantizedPartitioner))
            .check(["torch.ops.executorch_call_delegate"])
            .check_not(list(ops_after_quantization))
            .to_executorch()
            .serialize()
            .run_method()
            .compare_outputs()
        )
