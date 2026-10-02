from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cai_nghien_assistant.asr import configure_cuda_runtime


@unittest.skipUnless(os.name == "nt", "Windows CUDA runtime lookup")
class AsrRuntimeTests(unittest.TestCase):
    def test_configure_cuda_runtime_adds_wheel_dll_directories(self) -> None:
        site_packages = Path(tempfile.mkdtemp())
        cublas = site_packages / "nvidia/cublas/bin"
        cudnn = site_packages / "nvidia/cudnn/bin"
        cublas.mkdir(parents=True)
        cudnn.mkdir(parents=True)
        with patch("sysconfig.get_path", return_value=str(site_packages)), patch(
            "os.add_dll_directory"
        ) as add_directory, patch.dict(os.environ, {"PATH": "original"}):
            configure_cuda_runtime()
            self.assertTrue(os.environ["PATH"].startswith(f"{cublas};{cudnn};"))
            self.assertEqual(add_directory.call_count, 2)


if __name__ == "__main__":
    unittest.main()
