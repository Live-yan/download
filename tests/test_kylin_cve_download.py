import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "kylin-cve-download.py"
spec = importlib.util.spec_from_file_location("kylin_cve_download", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ResolverTests(unittest.TestCase):
    def test_parse_request_lines_and_commas(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "request.txt"
            path.write_text(
                "银河麒麟高级服务器操作系统 V10 SP3 2403\n"
                "CVE-2026-35386, CVE-2026-3497\n"
                "cve-2026-35386\n",
                encoding="utf-8",
            )
            system, arch, cves = module.parse_request(path, "auto")
            self.assertEqual(system, "银河麒麟高级服务器操作系统 V10 SP3 2403")
            self.assertEqual(arch, "aarch64")
            self.assertEqual(cves, ["CVE-2026-35386", "CVE-2026-3497"])

    def test_embedded_arch(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "request.txt"
            path.write_text("银河麒麟高级服务器操作系统 V10 SP3 | x86_64\nCVE-2026-35386\n", encoding="utf-8")
            _, arch, _ = module.parse_request(path, "auto")
            self.assertEqual(arch, "x86_64")

    def test_repo_alias_2309b(self):
        repo = module.resolve_repo("银河麒麟高级服务器操作系统 V10 SP3 2309B")
        self.assertEqual(repo.key, "v10sp3-2309b")

    def test_rpm_version_compare(self):
        self.assertGreater(module.rpmvercmp("16.p27.ky10", "16.p26.ky10"), 0)
        self.assertGreater(module.rpmvercmp("52.64.v2207", "52.60.v2207"), 0)
        self.assertLess(module.rpmvercmp("1.0~rc1", "1.0"), 0)

    def test_select_latest_same_binary_package(self):
        old = module.AdvisoryPackage("openssh", "0", "8.2p1", "16.p26.ky10", "aarch64", "old.rpm", {"A"}, {"CVE-1"})
        new = module.AdvisoryPackage("openssh", "0", "8.2p1", "16.p27.ky10", "aarch64", "new.rpm", {"B"}, {"CVE-2"})
        server = module.AdvisoryPackage("openssh-server", "0", "8.2p1", "16.p27.ky10", "aarch64", "server.rpm", {"B"}, {"CVE-2"})
        selected = module.select_latest([old, new, server])
        self.assertEqual([p.filename for p in selected], ["new.rpm", "server.rpm"])
        self.assertEqual(selected[0].cves, {"CVE-1", "CVE-2"})


if __name__ == "__main__":
    unittest.main()
