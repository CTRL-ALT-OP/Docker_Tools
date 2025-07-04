import os
import sys
import csv
import zipfile
import subprocess
import tempfile
import shutil
import time
import hashlib
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.commands import DOCKER_COMMANDS


class SimpleValidator:
    def __init__(self, cleanup: bool = True):
        self.cleanup = cleanup
        self.work_dir = Path(tempfile.mkdtemp(prefix="validation_"))
        self.results = []
        print(f"Working directory: {self.work_dir}")

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        if self.cleanup and self.work_dir.exists():
            print(f"Cleaning up: {self.work_dir}")
            shutil.rmtree(self.work_dir)

    def _resolve_path_conflicts(self, path: Path):
        """Resolve conflicts where a file exists with the same name as a needed directory"""
        parts = path.parts
        base_path = Path(parts[0])

        for i in range(1, len(parts)):
            current_path = base_path / Path(*parts[1 : i + 1])

            # If this path exists as a file but we need it as a directory
            if current_path.exists() and current_path.is_file():
                # Rename the conflicting file by adding .bak extension
                backup_path = current_path.with_suffix(current_path.suffix + ".bak")
                counter = 1
                while backup_path.exists():
                    backup_path = current_path.with_suffix(
                        f"{current_path.suffix}.bak{counter}"
                    )
                    counter += 1

                print(f"Resolving conflict: {current_path} -> {backup_path}")
                current_path.rename(backup_path)

    def extract_codebase(self, zip_path: Path) -> Tuple[Path, float]:
        """Extract ZIP file using hybrid approach: built-in first, manual if needed"""
        start_time = time.time()
        extract_dir = self.work_dir / zip_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting {zip_path.name}...")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Check if we need manual extraction
            windows_paths = [name for name in zip_ref.namelist() if "\\" in name]

            if windows_paths:
                print(
                    f"Found {len(windows_paths)} Windows-style paths, using manual extraction..."
                )
                self._extract_with_conflict_resolution(zip_ref, extract_dir)
            else:
                try:
                    # Try built-in extraction first (fastest)
                    zip_ref.extractall(extract_dir)
                except OSError as e:
                    if "Not a directory" in str(e):
                        print(f"Extraction conflict detected: {e}")
                        print(
                            "Falling back to manual extraction with conflict resolution..."
                        )
                        self._extract_with_conflict_resolution(zip_ref, extract_dir)
                    else:
                        raise

        self._normalize_scripts(extract_dir)

        extraction_time = time.time() - start_time
        print(f"✓ Extraction complete ({extraction_time:.1f}s)")

        return extract_dir, extraction_time

    def _extract_with_conflict_resolution(
        self, zip_ref: zipfile.ZipFile, extract_dir: Path
    ):
        """Manual extraction with path normalization and conflict resolution"""
        for member in zip_ref.infolist():
            # Skip directories
            if member.is_dir():
                continue

            normalized_path = member.filename.replace("\\", "/")
            target_path = extract_dir / normalized_path

            # Resolve any path conflicts before creating directories
            self._resolve_path_conflicts(target_path.parent)

            # Create parent directories
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, FileExistsError) as e:
                print(
                    f"Directory creation failed: {e}, attempting conflict resolution..."
                )
                self._resolve_path_conflicts(target_path.parent)
                target_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract the file content
            with zip_ref.open(member) as source, open(target_path, "wb") as target:
                target.write(source.read())

            # Set appropriate permissions
            if hasattr(member, "external_attr") and member.external_attr:
                permissions = (member.external_attr >> 16) & 0o777
                if permissions:
                    target_path.chmod(permissions)

    def _normalize_scripts(self, extract_dir: Path):
        """Normalize shell scripts for cross-platform consistency"""
        sh_files = list(extract_dir.glob("*.sh"))
        if sh_files:
            print(f"Processing {len(sh_files)} shell scripts...")

        for script in sh_files:
            try:
                content = script.read_bytes()
                has_cr = b"\r" in content

                if has_cr:
                    print(f"Fixing Windows line endings in {script.name}")
                    fixed_content = content.replace(b"\r\n", b"\n").replace(
                        b"\r", b"\n"
                    )
                    script.write_bytes(fixed_content)

                script.chmod(0o755)

            except Exception as e:
                print(f"Warning: Could not process script {script.name}: {e}")

    def build_docker_image(
        self, extract_dir: Path, image_name: str
    ) -> Tuple[bool, str, str, float]:
        """Build Docker image using build_docker.sh script"""
        build_script = extract_dir / "build_docker.sh"

        if not build_script.exists():
            return False, "", "No build_docker.sh script found", 0.0

        start_time = time.time()

        try:
            original_cwd = Path.cwd()
            os.chdir(extract_dir)

            print(f"Building Docker image: {image_name}")

            # Clean environment for consistency, but include Docker connection variables for DinD
            clean_env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "USER": os.environ.get("USER", ""),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "DOCKER_HOST": os.environ.get("DOCKER_HOST", ""),
                "DOCKER_CERT_PATH": os.environ.get("DOCKER_CERT_PATH", ""),
                "DOCKER_TLS_VERIFY": os.environ.get("DOCKER_TLS_VERIFY", ""),
            }

            result = subprocess.run(
                ["./build_docker.sh", image_name],
                capture_output=True,
                text=True,
                timeout=1200,
                env=clean_env,
            )

            os.chdir(original_cwd)
            build_time = time.time() - start_time

            if result.returncode == 0:
                # Verify that the Docker image was actually created
                image_exists = self._verify_docker_image_exists(image_name)
                if image_exists:
                    print(f"✓ Build successful: {image_name} ({build_time:.1f}s)")
                    return True, result.stdout, result.stderr, build_time
                else:
                    print(
                        f"✗ Build script succeeded but image not found: {image_name} ({build_time:.1f}s)"
                    )
                    return (
                        False,
                        result.stdout,
                        result.stderr
                        + "\nError: Docker image was not created despite successful build script",
                        build_time,
                    )
            else:
                print(f"✗ Build failed: {image_name} ({build_time:.1f}s)")
                print(f"Build stdout: {result.stdout}")
                print(f"Build stderr: {result.stderr}")
                print(f"Return code: {result.returncode}")
                return False, result.stdout, result.stderr, build_time

        except subprocess.TimeoutExpired:
            os.chdir(original_cwd)
            build_time = time.time() - start_time
            return False, "", "Build timed out", build_time
        except Exception as e:
            os.chdir(original_cwd)
            build_time = time.time() - start_time
            return False, "", f"Build error: {str(e)}", build_time

    def _verify_docker_image_exists(self, image_name: str) -> bool:
        """Verify that a Docker image exists"""
        try:
            cmd = [
                part.format(image_name=image_name) if "{image_name}" in part else part
                for part in DOCKER_COMMANDS["images"]
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0 and result.stdout.strip() != ""
        except Exception:
            return False

    def run_tests(
        self, image_name: str, extract_dir: Path
    ) -> Tuple[bool, str, str, float]:
        """Run tests using the Docker image"""
        start_time = time.time()

        try:
            original_cwd = Path.cwd()
            os.chdir(extract_dir)

            print(f"Running tests for: {image_name}")

            # Clean environment for consistency, but include Docker connection variables for DinD
            clean_env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "USER": os.environ.get("USER", ""),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "DOCKER_HOST": os.environ.get("DOCKER_HOST", ""),
                "DOCKER_CERT_PATH": os.environ.get("DOCKER_CERT_PATH", ""),
                "DOCKER_TLS_VERIFY": os.environ.get("DOCKER_TLS_VERIFY", ""),
            }

            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{extract_dir}:/app",
                    "-w",
                    "/app",
                    image_name,
                    "./run_tests.sh",
                ],
                capture_output=True,
                text=True,
                timeout=1200,
                env=clean_env,
            )

            os.chdir(original_cwd)
            test_time = time.time() - start_time

            if result.returncode == 0:
                print(f"✓ Tests passed: {image_name} ({test_time:.1f}s)")
                return True, result.stdout, result.stderr, test_time
            else:
                print(f"✗ Tests failed: {image_name} ({test_time:.1f}s)")
                print(f"Test stdout: {result.stdout}")
                print(f"Test stderr: {result.stderr}")
                print(f"Return code: {result.returncode}")
                return False, result.stdout, result.stderr, test_time

        except subprocess.TimeoutExpired:
            os.chdir(original_cwd)
            test_time = time.time() - start_time
            return False, "", "Tests timed out", test_time
        except Exception as e:
            os.chdir(original_cwd)
            test_time = time.time() - start_time
            return False, "", f"Test error: {str(e)}", test_time

    def cleanup_docker_image(self, image_name: str):
        """Clean up Docker image"""
        try:
            cmd = [
                part.format(image_name=image_name) if "{image_name}" in part else part
                for part in DOCKER_COMMANDS["rmi"]
            ]
            subprocess.run(cmd, capture_output=True, timeout=60)
            print(f"✓ Cleaned up image: {image_name}")
        except Exception as e:
            print(f"Warning: Could not clean up image {image_name}: {e}")

    def validate_codebase(self, zip_path: Path) -> Dict:
        """Main validation function - extracts, builds, and tests a codebase"""
        codebase_name = zip_path.stem

        # Create deterministic image name using file hash for consistent results
        with open(zip_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        image_name = f"validation-{file_hash}"

        print(f"\n{'='*50}")
        print(f"Validating: {codebase_name}")
        print(f"{'='*50}")

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
        }

        try:
            # Extract codebase
            extract_dir, extraction_time = self.extract_codebase(zip_path)
            result["extraction_success"] = True
            result["extraction_time"] = extraction_time

            # Find scripts
            build_script = extract_dir / "build_docker.sh"
            test_script = extract_dir / "run_tests.sh"

            result["build_script_present"] = build_script.exists()
            result["test_script_present"] = test_script.exists()

            if not result["build_script_present"]:
                result["error_message"] = "Missing build_docker.sh"
                return result

            if not result["test_script_present"]:
                result["error_message"] = "Missing run_tests.sh"
                return result

            # Build Docker image
            build_success, build_stdout, build_stderr, build_time = (
                self.build_docker_image(extract_dir, image_name)
            )
            result["build_success"] = build_success
            result["build_output"] = build_stdout
            result["build_error"] = build_stderr
            result["build_time"] = build_time

            if not build_success:
                result["error_message"] = "Docker build failed"
                return result

            # Run tests
            test_success, test_stdout, test_stderr, exec_time = self.run_tests(
                image_name, extract_dir
            )
            result["test_success"] = test_success
            result["test_output"] = test_stdout
            result["test_error"] = test_stderr
            result["test_execution_time"] = exec_time

            if not test_success:
                result["error_message"] = "Tests failed"

            # Cleanup
            if self.cleanup:
                self.cleanup_docker_image(image_name)

        except Exception as e:
            result["error_message"] = str(e)
            print(f"Error: {e}")

        self.results.append(result)
        return result

    def validate_codebase_with_progress(
        self, zip_path: Path, progress, codebase_type: str = "rewrite"
    ) -> Dict:
        """Main validation function with progress updates - extracts, builds, and tests a codebase"""
        codebase_name = zip_path.stem

        # Create deterministic image name using file hash for consistent results
        with open(zip_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        image_name = f"validation-{file_hash}"

        print(f"\n{'='*50}")
        print(f"Validating: {codebase_name} ({codebase_type})")
        print(f"{'='*50}")

        result = {
            "codebase_name": codebase_name,
            "zip_file": zip_path.name,
            "timestamp": datetime.now().isoformat(),
            "codebase_type": codebase_type,
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
            "validation_success": False,
        }

        try:
            # Extract codebase
            progress.status = "extracting"
            progress.message = "Extracting codebase..."
            progress.progress = 10

            extract_dir, extraction_time = self.extract_codebase(zip_path)
            result["extraction_success"] = True
            result["extraction_time"] = extraction_time
            progress.timing["extraction_time"] = extraction_time

            progress.message = f"Extraction complete ({extraction_time:.1f}s)"
            progress.progress = 20

            # Find scripts
            build_script = extract_dir / "build_docker.sh"
            test_script = extract_dir / "run_tests.sh"

            result["build_script_present"] = build_script.exists()
            result["test_script_present"] = test_script.exists()

            if not result["build_script_present"]:
                result["error_message"] = "Missing build_docker.sh"
                return result

            if not result["test_script_present"]:
                result["error_message"] = "Missing run_tests.sh"
                return result

            # Build Docker image
            progress.status = "building"
            progress.message = "Building Docker image..."
            progress.progress = 30

            build_success, build_stdout, build_stderr, build_time = (
                self.build_docker_image(extract_dir, image_name)
            )
            result["build_success"] = build_success
            result["build_output"] = build_stdout
            result["build_error"] = build_stderr
            result["build_time"] = build_time
            progress.timing["build_time"] = build_time

            if build_success:
                progress.message = f"Build complete ({build_time:.1f}s)"
                progress.progress = 60
            else:
                result["error_message"] = "Docker build failed"
                return result

            # Run tests
            progress.status = "testing"
            progress.message = "Running tests..."
            progress.progress = 70

            test_success, test_stdout, test_stderr, exec_time = self.run_tests(
                image_name, extract_dir
            )
            result["test_success"] = test_success
            result["test_output"] = test_stdout
            result["test_error"] = test_stderr
            result["test_execution_time"] = exec_time
            progress.timing["test_time"] = exec_time

            if test_success:
                progress.message = f"Tests complete ({exec_time:.1f}s)"
                progress.progress = 90
            else:
                # For preedit and postedit, test failures are acceptable
                if codebase_type in ["preedit", "postedit"]:
                    progress.message = f"Tests complete ({exec_time:.1f}s) - Test failures allowed for {codebase_type}"
                else:
                    result["error_message"] = "Tests failed"

            # Determine validation success based on codebase type
            if codebase_type == "rewrite":
                # For rewrite: build must pass AND all tests must pass
                result["validation_success"] = (
                    result["build_success"] and result["test_success"]
                )
            else:
                # For preedit and postedit: only build must pass, tests can fail
                result["validation_success"] = result["build_success"]

            # Update final message based on validation success
            if result["validation_success"]:
                if codebase_type == "rewrite":
                    progress.message = "Validation successful - Build and tests passed"
                else:
                    progress.message = (
                        f"Validation successful - Build passed ({codebase_type})"
                    )

            # Cleanup
            if self.cleanup:
                progress.message = "Cleaning up..."
                progress.progress = 95
                self.cleanup_docker_image(image_name)

        except Exception as e:
            result["error_message"] = str(e)
            print(f"Error: {e}")

        self.results.append(result)
        return result

    def save_results_csv(self, output_path: str = "validation_results.csv"):
        """Save detailed results to CSV for debugging"""
        if not self.results:
            print("No results to save")
            return

        fieldnames = [
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
            "build_time",
            "extraction_time",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)

        print(f"Detailed results saved to {output_path}")


def main():
    if len(sys.argv) not in [2, 3]:
        print("Usage: python validator.py <path_to_zip_file> [output.csv]")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_csv = sys.argv[2] if len(sys.argv) == 3 else "validation_results.csv"

    if not zip_path.exists():
        print(f"Error: ZIP file not found: {zip_path}")
        sys.exit(1)

    # Check Docker availability and platform support
    try:
        subprocess.run(DOCKER_COMMANDS["version"], capture_output=True, check=True)
        result = subprocess.run(DOCKER_COMMANDS["info"], capture_output=True, text=True)
        if "linux/amd64" not in result.stdout:
            print("Warning: linux/amd64 platform may not be available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "Error: Docker is not available. Please install Docker and ensure it's running."
        )
        sys.exit(1)

    # Run validation
    with SimpleValidator() as validator:
        result = validator.validate_codebase(zip_path)

        # Save to csv
        validator.save_results_csv(output_csv)

        print(f"\n{'='*50}")
        print("VALIDATION SUMMARY")
        print(f"{'='*50}")
        print(f"Codebase: {result['codebase_name']}")
        print(f"Build: {'✓' if result['build_success'] else '✗'}")
        print(f"Tests: {'✓' if result['test_success'] else '✗'}")
        if result["test_success"]:
            print(f"Execution time: {result['test_execution_time']:.1f}s")
        if result["error_message"]:
            print(f"Error: {result['error_message']}")
        print(f"Results saved to: {output_csv}")
        print(f"{'='*50}")

        if result["build_success"] and result["test_success"]:
            print("SUCCESS: Validation passed!")
            sys.exit(0)
        else:
            print("FAILED: Validation failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
