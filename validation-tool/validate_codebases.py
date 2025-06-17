import os
import sys
import csv
import shutil
import zipfile
import logging
import argparse
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CodebaseValidator:
    def __init__(self, codebases_dir: str = "codebases", cleanup: bool = True):
        self.codebases_dir = Path(codebases_dir)
        self.cleanup = cleanup
        self.work_dir = Path(tempfile.mkdtemp(prefix="codebase_validation_"))
        self.results = []
        self.extracted_codebases = {}
        self.unique_validation_id = None

        logger.info(f"Working directory: {self.work_dir}")

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        if self.cleanup and self.work_dir.exists():
            logger.info(f"Cleaning up work directory: {self.work_dir}")
            shutil.rmtree(self.work_dir)

    def find_zip_files(self, filter_type: str = None) -> List[Path]:
        if not self.codebases_dir.exists():
            raise FileNotFoundError(
                f"Codebases directory not found: {self.codebases_dir}"
            )

        zip_files = list(self.codebases_dir.glob("*.zip"))

        if filter_type:
            filtered_files = []
            for zip_file in zip_files:
                name_lower = zip_file.stem.lower()
                if filter_type == "preedit" and "preedit" in name_lower:
                    filtered_files.append(zip_file)
                elif filter_type == "postedit-beetle" and "beetle" in name_lower:
                    filtered_files.append(zip_file)
                elif filter_type == "postedit-sonnet" and "sonnet" in name_lower:
                    filtered_files.append(zip_file)
                elif filter_type == "rewrite" and "rewrite" in name_lower:
                    filtered_files.append(zip_file)
            zip_files = filtered_files

            if not zip_files:
                logger.warning(
                    f"No ZIP files found matching filter '{filter_type}' in {self.codebases_dir}"
                )
            else:
                logger.info(
                    f"Found {len(zip_files)} ZIP files matching filter '{filter_type}' in {self.codebases_dir}"
                )
        else:
            logger.info(f"Found {len(zip_files)} ZIP files in {self.codebases_dir}")

        return zip_files

    def extract_codebase(self, zip_path: Path) -> Path:
        extract_dir = self.work_dir / zip_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Extracting {zip_path.name} to {extract_dir}")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            windows_paths = [name for name in zip_ref.namelist() if "\\" in name]
            if windows_paths:
                logger.info(
                    f"Found {len(windows_paths)} Windows-style paths, normalizing..."
                )
                self._extract_with_path_normalization(zip_ref, extract_dir)
            else:
                zip_ref.extractall(extract_dir)

        return extract_dir

    def _extract_with_path_normalization(
        self, zip_ref: zipfile.ZipFile, extract_dir: Path
    ):
        for member in zip_ref.infolist():
            normalized_path = member.filename.replace("\\", "/")

            if normalized_path.endswith("/"):
                continue

            target_path = extract_dir / normalized_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with zip_ref.open(member) as source, open(target_path, "wb") as target:
                target.write(source.read())

            original_mode = member.external_attr >> 16
            if original_mode and (original_mode & 0o111):
                target_path.chmod(0o755)
            else:
                target_path.chmod(0o644)

            logger.debug(
                f"Extracted and normalized: {member.filename} -> {normalized_path}"
            )

    def make_scripts_executable(self, extract_dir: Path):
        sh_files = list(extract_dir.glob("*.sh"))
        logger.info(f"Found {len(sh_files)} shell scripts to process")

        for script in sh_files:
            try:
                content = script.read_bytes()
                has_cr = b"\r" in content

                if has_cr:
                    logger.info(f"Fixing Windows line endings in {script.name}")
                    fixed_content = content.replace(b"\r\n", b"\n").replace(
                        b"\r", b"\n"
                    )
                    script.write_bytes(fixed_content)

            except Exception as e:
                logger.warning(f"Could not fix script content in {script.name}: {e}")

            script.chmod(0o755)
            logger.debug(f"Made {script.name} executable")

    def build_docker_image(
        self, extract_dir: Path, image_name: str
    ) -> Tuple[bool, str, str, str]:
        build_script_path = extract_dir / "build_docker.sh"

        if not build_script_path.exists():
            return (
                False,
                "",
                "No build_docker.sh script found in codebase root",
                image_name,
            )

        try:
            original_cwd = Path.cwd()
            os.chdir(extract_dir)

            actual_image_name = image_name

            try:
                script_content = build_script_path.read_text()
                import re

                match = re.search(r'IMAGE_NAME="([^"]+)"', script_content)
                if match:
                    actual_image_name = match.group(1)
                    logger.debug(f"Found image name in script: {actual_image_name}")
            except Exception as e:
                logger.warning(f"Could not parse build script: {e}")

            logger.info(
                f"Building Docker image using build_docker.sh (will create: {actual_image_name})"
            )
            result = subprocess.run(
                ["./build_docker.sh", image_name],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0 and actual_image_name != image_name:
                logger.info(f"Tagging {actual_image_name} as {image_name}")
                tag_result = subprocess.run(
                    ["docker", "tag", actual_image_name, image_name],
                    capture_output=True,
                    text=True,
                )
                if tag_result.returncode != 0:
                    logger.warning(f"Failed to tag image: {tag_result.stderr}")
                    image_name = actual_image_name

            os.chdir(original_cwd)

            if result.returncode == 0:
                logger.info(f"Successfully built Docker image: {image_name}")

                combined_output = result.stdout + (
                    "\n" + result.stderr if result.stderr else ""
                )
                return True, combined_output, "", image_name
            else:
                logger.error(f"Failed to build Docker image: {image_name}")
                return False, result.stdout, result.stderr, image_name

        except subprocess.TimeoutExpired:
            os.chdir(original_cwd)
            return False, "", "Docker build timed out", image_name
        except Exception as e:
            os.chdir(original_cwd)
            return False, "", f"Build error: {str(e)}", image_name

    def run_tests(
        self, image_name: str, extract_dir: Path
    ) -> Tuple[bool, str, str, float]:
        test_script = extract_dir / "run_tests.sh"

        if not test_script.exists():
            return False, "", "No run_tests.sh script found in codebase root", 0.0

        start_time = time.time()

        try:
            logger.info(f"Running tests for {image_name} using run_tests.sh")
            result = subprocess.run(
                ["docker", "run", "--rm", image_name, "./run_tests.sh"],
                capture_output=True,
                text=True,
                timeout=180,
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                logger.info(f"Tests passed for {image_name}")
                combined_output = result.stdout + (
                    "\n" + result.stderr if result.stderr else ""
                )
                return True, combined_output, "", execution_time
            else:
                logger.warning(f"Tests failed for {image_name}")
                return False, result.stdout, result.stderr, execution_time

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return False, "", "Test execution timed out", execution_time
        except Exception as e:
            execution_time = time.time() - start_time
            return False, "", f"Test error: {str(e)}", execution_time

    def cleanup_docker_image(self, image_name: str):
        try:
            subprocess.run(
                ["docker", "rmi", image_name], capture_output=True, check=False
            )
            logger.debug(f"Removed Docker image: {image_name}")
        except Exception as e:
            logger.warning(f"Could not remove Docker image {image_name}: {e}")

    def compute_file_hash(self, file_path: Path) -> str:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def generate_unique_validation_id(self, zip_files: List[Path]) -> str:
        if not zip_files:
            return hashlib.sha256(b"no_codebases").hexdigest()[:16]

        file_hashes = []
        for zip_path in zip_files:
            try:
                file_hash = self.compute_file_hash(zip_path)
                file_hashes.append(file_hash)
            except Exception as e:
                logger.warning(f"Could not hash {zip_path.name}: {e}")
                file_size = zip_path.stat().st_size
                file_hashes.append(f"size_{file_size}")

        file_hashes.sort()
        combined_data = "|".join(file_hashes)
        final_hash = hashlib.sha256(combined_data.encode("utf-8")).hexdigest()

        return final_hash[:16]

    def validate_codebase(self, zip_path: Path) -> Dict:
        codebase_name = zip_path.stem
        image_name = f"validation_{codebase_name}".lower().replace("_", "-")

        logger.info(f"Processing codebase: {codebase_name}")

        result = {
            "codebase_name": codebase_name,
            "zip_file": zip_path.name,
            "timestamp": datetime.now().isoformat(),
            "extraction_success": False,
            "build_script_present": False,
            "test_script_present": False,
            "build_success": False,
            "test_success": False,
            "test_execution_time": 0.0,
            "build_output": "",
            "build_error": "",
            "test_output": "",
            "test_error": "",
            "docker_image": image_name,
            "error_message": "",
            "differs_from_preedit": False,
            "differs_from_beetle": False,
            "differs_from_sonnet": False,
            "differs_from_rewrite": False,
            "comparison_errors": "",
            "diff_vs_preedit": "",
            "diff_vs_beetle": "",
            "diff_vs_sonnet": "",
            "diff_vs_rewrite": "",
        }

        try:

            extract_dir = self.extract_codebase(zip_path)
            result["extraction_success"] = True

            self.extracted_codebases[codebase_name] = extract_dir

            build_script_path = extract_dir / "build_docker.sh"
            test_script_path = extract_dir / "run_tests.sh"

            result["build_script_present"] = build_script_path.exists()
            result["test_script_present"] = test_script_path.exists()

            missing_files = []
            if not result["build_script_present"]:
                missing_files.append("build_docker.sh")
            if not result["test_script_present"]:
                missing_files.append("run_tests.sh")

            if missing_files:
                result["error_message"] = (
                    f"Missing required files in codebase root: {', '.join(missing_files)}"
                )
                logger.error(
                    f"Codebase {codebase_name} is missing required files: {', '.join(missing_files)}"
                )
                return result

            self.make_scripts_executable(extract_dir)

            build_success, build_stdout, build_stderr, actual_image_name = (
                self.build_docker_image(extract_dir, image_name)
            )
            result["build_success"] = build_success
            result["build_output"] = build_stdout
            result["build_error"] = build_stderr
            result["docker_image"] = actual_image_name

            if build_success:
                test_success, test_stdout, test_stderr, exec_time = self.run_tests(
                    actual_image_name, extract_dir
                )
                result["test_success"] = test_success
                result["test_output"] = test_stdout
                result["test_error"] = test_stderr
                result["test_execution_time"] = exec_time

                if self.cleanup:
                    self.cleanup_docker_image(actual_image_name)
                    if actual_image_name != image_name:
                        self.cleanup_docker_image(image_name)
            else:
                result["error_message"] = "Docker build failed"

        except Exception as e:
            result["error_message"] = str(e)
            logger.error(f"Error processing {codebase_name}: {e}")

        return result

    def validate_all_codebases(self, filter_type: str = None) -> List[Dict]:
        zip_files = self.find_zip_files(filter_type)

        if not zip_files:
            if filter_type:
                logger.warning(f"No ZIP files found matching filter '{filter_type}'")
            else:
                logger.warning("No ZIP files found in codebases directory")
            return []

        if not filter_type:
            self.unique_validation_id = self.generate_unique_validation_id(zip_files)
            logger.info(f"Unique Validation ID: {self.unique_validation_id}")

        for zip_path in zip_files:
            result = self.validate_codebase(zip_path)
            self.results.append(result)

        if not filter_type:
            self.analyze_codebase_differences()

        return self.results

    def save_results_csv(self, output_path: str = "validation_results.csv"):
        if not self.results:
            logger.warning("No results to save")
            return

        fieldnames = [
            "unique_validation_id",
            "codebase_name",
            "zip_file",
            "timestamp",
            "extraction_success",
            "build_script_present",
            "test_script_present",
            "build_success",
            "test_success",
            "test_execution_time",
            "docker_image",
            "error_message",
            "build_output",
            "build_error",
            "test_output",
            "test_error",
            "differs_from_preedit",
            "differs_from_beetle",
            "differs_from_sonnet",
            "differs_from_rewrite",
            "comparison_errors",
            "diff_vs_preedit",
            "diff_vs_beetle",
            "diff_vs_sonnet",
            "diff_vs_rewrite",
        ]

        for result in self.results:
            result["unique_validation_id"] = (
                self.unique_validation_id if self.unique_validation_id else ""
            )

        def get_codebase_type_order(result):
            name = result["codebase_name"].lower()
            if "preedit" in name:
                return 0
            elif "beetle" in name:
                return 1
            elif "sonnet" in name:
                return 2
            elif "rewrite" in name:
                return 3
            else:
                return 4

        sorted_results = sorted(self.results, key=get_codebase_type_order)

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted_results)

        logger.info(f"Results saved to {output_path}")

    def print_validation_id_box(self):
        if not self.unique_validation_id:
            return

        print(f"UNIQUE VALIDATION ID: {self.unique_validation_id}")

        print("\n" + "╔" + "═" * 76 + "╗")
        print("║" + " " * 76 + "║")
        print(
            "║"
            + "                     VALIDATION COMPLETE                     ".center(76)
            + "║"
        )
        print("║" + " " * 76 + "║")
        print(
            "║"
            + "  📋 Your Unique Validation ID (copy this):                  ".ljust(75)
            + "║"
        )
        print("║" + " " * 76 + "║")
        print("║" + f"      {self.unique_validation_id}".ljust(76) + "║")
        print("║" + " " * 76 + "║")
        print(
            "║"
            + "  ⚠️  IMPORTANT: Save this ID! You'll need it for submission.  ".ljust(77)
            + "║"
        )
        print("║" + " " * 76 + "║")
        print("╚" + "═" * 76 + "╝")
        print()

    def print_summary(self):
        if not self.results:
            logger.info("No results to summarize")
            return

        total = len(self.results)
        build_success = sum(1 for r in self.results if r["build_success"])
        test_success = sum(1 for r in self.results if r["test_success"])

        print(f"\n{'='*60}")
        print(f"CODEBASE VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(
            f"Total: {total} | Build: {build_success}/{total} | Tests: {test_success}/{total}"
        )
        print(f"{'='*60}")

        results_by_type = {}
        for result in self.results:
            name = result["codebase_name"].lower()
            if "preedit" in name:
                results_by_type["preedit"] = result
            elif "beetle" in name:
                results_by_type["beetle"] = result
            elif "sonnet" in name:
                results_by_type["sonnet"] = result
            elif "rewrite" in name:
                results_by_type["rewrite"] = result

        for codebase_type in ["preedit", "beetle", "sonnet", "rewrite"]:
            if codebase_type in results_by_type:
                result = results_by_type[codebase_type]

                build_status = "✓" if result["build_success"] else "✗"

                if result["build_success"]:
                    test_status = "✓" if result["test_success"] else "✗"
                    runtime = f"{result['test_execution_time']:.1f}s"
                    print(
                        f"{build_status} Build | {test_status} Tests ({runtime}) - {result['codebase_name']}"
                    )
                else:
                    print(
                        f"{build_status} Build | ~ Tests (~) - {result['codebase_name']}"
                    )
                    if result["error_message"]:
                        print(f"  Error: {result['error_message']}")

        print(f"{'='*60}")

        preedit = results_by_type.get("preedit")
        rewrite = results_by_type.get("rewrite")

        if preedit and preedit["test_success"]:
            print(
                "⚠️  WARNING: All tests passing in preedit. You need to include tests that fail, not all tests need to be P2P."
            )

        if rewrite and not rewrite["test_success"] and rewrite["build_success"]:
            print(
                "⚠️  WARNING: Your rewrite code has failing tests. Please fix before submitting."
            )

        failed_builds = [
            r["codebase_name"] for r in self.results if not r["build_success"]
        ]
        if failed_builds:
            print(f"⚠️  WARNING: Build failures: {', '.join(failed_builds)}")

        beetle = results_by_type.get("beetle")
        sonnet = results_by_type.get("sonnet")
        if (
            beetle
            and sonnet
            and beetle["extraction_success"]
            and sonnet["extraction_success"]
        ):
            if not beetle["differs_from_sonnet"]:
                print(
                    "⚠️  WARNING: postedit-beetle and postedit-sonnet codebases are identical. You may have uploaded the same codebase twice."
                )

        if preedit and preedit["extraction_success"]:
            identical_to_preedit = []
            for codebase_type in ["beetle", "sonnet", "rewrite"]:
                if codebase_type in results_by_type:
                    result = results_by_type[codebase_type]
                    if (
                        result["extraction_success"]
                        and not result["differs_from_preedit"]
                    ):
                        identical_to_preedit.append(codebase_type)

            if identical_to_preedit:
                codebase_names = ", ".join(
                    [
                        f"postedit-{name}" if name in ["beetle", "sonnet"] else name
                        for name in identical_to_preedit
                    ]
                )
                print(
                    f"⚠️  WARNING: The following codebases are identical to preedit: {codebase_names}. You may have forgotten to apply changes or uploaded the wrong codebase."
                )

        print(f"{'='*60}")
        print()

        if self.unique_validation_id:
            self.print_validation_id_box()

    def compare_codebases(self, base_name: str, compare_name: str) -> Dict[str, bool]:
        base_path = self.extracted_codebases.get(base_name)
        compare_path = self.extracted_codebases.get(compare_name)

        if not base_path or not compare_path:
            return {
                "has_differences": False,
                "comparison_error": True,
                "diff_output": "",
            }

        try:
            import subprocess

            diff_result = subprocess.run(
                ["diff", "-r", str(base_path), str(compare_path)],
                capture_output=True,
                text=True,
            )

            has_differences = diff_result.returncode == 1
            comparison_error = diff_result.returncode > 1

            diff_output = diff_result.stdout
            if len(diff_output) > 5000:
                diff_output = diff_output[:5000] + "... [truncated]"

            return {
                "has_differences": has_differences,
                "comparison_error": comparison_error,
                "diff_output": diff_output,
            }

        except Exception as e:
            logger.warning(f"Error comparing {base_name} and {compare_name}: {e}")
            return {
                "has_differences": False,
                "comparison_error": True,
                "diff_output": f"Error: {str(e)}",
            }

    def analyze_codebase_differences(self) -> None:
        codebase_names = [
            r["codebase_name"] for r in self.results if r["extraction_success"]
        ]

        preedit_name = None
        beetle_name = None
        sonnet_name = None
        rewrite_name = None

        for name in codebase_names:
            if "preedit" in name.lower():
                preedit_name = name
            elif "beetle" in name.lower():
                beetle_name = name
            elif "sonnet" in name.lower():
                sonnet_name = name
            elif "rewrite" in name.lower():
                rewrite_name = name

        for result in self.results:
            name = result["codebase_name"]

            if not result["extraction_success"]:
                continue

            comparison_errors = []

            if preedit_name and name != preedit_name:
                comparison = self.compare_codebases(preedit_name, name)
                result["differs_from_preedit"] = comparison["has_differences"]
                result["diff_vs_preedit"] = comparison["diff_output"]
                if comparison["comparison_error"]:
                    comparison_errors.append("preedit_comparison_failed")

            if beetle_name and name != beetle_name:
                comparison = self.compare_codebases(beetle_name, name)
                result["differs_from_beetle"] = comparison["has_differences"]
                result["diff_vs_beetle"] = comparison["diff_output"]
                if comparison["comparison_error"]:
                    comparison_errors.append("beetle_comparison_failed")

            if sonnet_name and name != sonnet_name:
                comparison = self.compare_codebases(sonnet_name, name)
                result["differs_from_sonnet"] = comparison["has_differences"]
                result["diff_vs_sonnet"] = comparison["diff_output"]
                if comparison["comparison_error"]:
                    comparison_errors.append("sonnet_comparison_failed")

            if rewrite_name and name != rewrite_name:
                comparison = self.compare_codebases(rewrite_name, name)
                result["differs_from_rewrite"] = comparison["has_differences"]
                result["diff_vs_rewrite"] = comparison["diff_output"]
                if comparison["comparison_error"]:
                    comparison_errors.append("rewrite_comparison_failed")

            result["comparison_errors"] = ";".join(comparison_errors)


def main():
    parser = argparse.ArgumentParser(description="Validate codebases using Docker")
    parser.add_argument(
        "--output", "-o", default="validation_results.csv", help="Output CSV file"
    )
    parser.add_argument(
        "--codebases-dir", default="codebases", help="Directory containing ZIP files"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't cleanup temporary files and Docker images",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    codebase_group = parser.add_mutually_exclusive_group()
    codebase_group.add_argument(
        "--preedit", action="store_true", help="Validate only preedit codebase"
    )
    codebase_group.add_argument(
        "--postedit-beetle",
        action="store_true",
        help="Validate only postedit-beetle codebase",
    )
    codebase_group.add_argument(
        "--postedit-sonnet",
        action="store_true",
        help="Validate only postedit-sonnet codebase",
    )
    codebase_group.add_argument(
        "--rewrite", action="store_true", help="Validate only rewrite codebase"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    filter_type = None
    if args.preedit:
        filter_type = "preedit"
    elif args.postedit_beetle:
        filter_type = "postedit-beetle"
    elif args.postedit_sonnet:
        filter_type = "postedit-sonnet"
    elif args.rewrite:
        filter_type = "rewrite"

    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error(
            "Docker is not available. Please install Docker and ensure it's running."
        )
        sys.exit(1)

    try:
        with CodebaseValidator(
            codebases_dir=args.codebases_dir, cleanup=not args.no_cleanup
        ) as validator:

            if filter_type:
                logger.info(f"Starting validation for {filter_type} codebase only...")
            else:
                logger.info("Starting codebase validation...")
            results = validator.validate_all_codebases(filter_type)

            if results:
                validator.save_results_csv(args.output)
                validator.print_summary()
            else:
                if filter_type:
                    logger.error(
                        f"No {filter_type} codebase was processed successfully"
                    )
                else:
                    logger.error("No codebases were processed successfully")
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
