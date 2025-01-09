import os
import shutil
import subprocess
import tempfile
import git
import pandas as pd
import argparse


parser = argparse.ArgumentParser()
parser.add_argument('--num_rows', type=int, default=None,
                   help='Number of rows to process. If None, process all rows.')
args = parser.parse_args()

# Load dataset
dataset_path = "SWE-bench_dev.csv"
data = pd.read_csv(dataset_path)

# GitHub token (if needed for private repos)
GITHUB_TOKEN = "your_github_token"

def install_dependencies(temp_dir):
    """Install project dependencies from various possible requirement files."""
    print("\n=== Installing Dependencies ===")
    # Check for different requirements files
    req_files = [
        "requirements_dev.txt",
        "requirements-dev.txt",
        "dev-requirements.txt",
        "test-requirements.txt",
        "requirements.txt"
    ]

    for req_file in req_files:
        if os.path.exists(os.path.join(temp_dir, req_file)):
            print(f"Installing from {req_file}...")
            try:
                subprocess.run(
                    ["pip", "install", "-r", req_file],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                print(f"Warning: Failed to install some requirements from {req_file}: {e.stderr}")

    # Install package in editable mode if setup.py exists
    if os.path.exists(os.path.join(temp_dir, "setup.py")):
        print("Installing package in editable mode...")
        try:
            subprocess.run(
                ["pip", "install", "-e", "."],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install package: {e.stderr}")

# Function to process a single dataset row
def process_instance(row):
    repo_url = f"https://github.com/{row['repo']}"
    problem_statement = row["problem_statement"]
    patch_content = row["patch"]
    test_patch_content = row["test_patch"]
    env_commit = row["base_commit"]
    # env_commit = row["environment_setup_commit"]
    fail_to_pass = row["FAIL_TO_PASS"]
    pass_to_pass = row["PASS_TO_PASS"]

    # Step 1: Clone the repository into a temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        print(f"Cloning {repo_url} into {temp_dir}")
        repo = git.Repo.clone_from(repo_url, temp_dir)

        # Checkout the base commit if it exists
        if env_commit:
            repo.git.checkout(env_commit)

        # Step 2: Apply the patch
        patch_file = os.path.join(temp_dir, "fix.patch")
        test_patch_file = os.path.join(temp_dir, "test_patch.patch")
        with open(patch_file, "w") as f:
            f.write(patch_content)
        with open(test_patch_file, "w") as f:
            f.write(test_patch_content)

        print("Applying patch...")
        subprocess.run(["git", "apply", "fix.patch"], cwd=temp_dir, check=True)
        subprocess.run(["git", "apply", "test_patch.patch"], cwd=temp_dir, check=True)

        # After applying the patch, show the changes
        print("\n=== Files changed after applying patch ===")

        # Show git status
        print("\nGit Status:")
        status_output = subprocess.run(["git", "status"],
                                     cwd=temp_dir,
                                     capture_output=True,
                                     text=True)
        print(status_output.stdout)

        # Show diff of changes
        print("\nDetailed Changes:")
        diff_output = subprocess.run(["git", "diff"],
                                   cwd=temp_dir,
                                   capture_output=True,
                                   text=True)
        print(diff_output.stdout)

        # After applying patches and before running tests
        install_dependencies(temp_dir)

        # Run each test individually
        print("\n=== Running Tests ===")



        # Parse the test strings into lists
        fail_to_pass_tests = eval(fail_to_pass) if fail_to_pass else []
        pass_to_pass_tests = eval(pass_to_pass) if pass_to_pass else []

        test_counter = {
            "passed": 0,
            "failed": {
                "total": 0,
                "names": []
            },
            "skipped": {
                "total": 0,
                "names": []
            },
            "total": 0
        }

        test_results = {}

        print("\nRunning FAIL_TO_PASS tests:")
        for test in fail_to_pass_tests:
            print(f"\nRunning test: {test}")
            result = subprocess.run(
                ["pytest", test, "-v"],
                cwd=temp_dir,
                capture_output=True,
                text=True
            )
            test_results[f"fail_to_pass_{test}"] = {
                "passed": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
            print(f"Test {'PASSED' if result.returncode == 0 else 'FAILED'}")
            print(result.stdout)
            if result.returncode == 0:
                test_counter["passed"] += 1
                test_counter["total"] += 1
            elif result.returncode == 4:
                test_counter["skipped"]["total"] += 1
                test_counter["skipped"]["names"].append(test)
                test_counter["total"] += 1
            else:
                test_counter["failed"]["total"] += 1
                test_counter["failed"]["names"].append(test)
                test_counter["total"] += 1

        print("\nRunning PASS_TO_PASS tests:")
        for test in pass_to_pass_tests:
            print(f"\nRunning test: {test}")
            result = subprocess.run(
                ["pytest", test, "-v"],
                cwd=temp_dir,
                capture_output=True,
                text=True
            )
            test_results[f"pass_to_pass_{test}"] = {
                "passed": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
            print(f"Test {'PASSED' if result.returncode == 0 else 'FAILED'}")
            print(result.stdout)
            if result.returncode == 0:
                test_counter["passed"] += 1
                test_counter["total"] += 1
            elif result.returncode == 4:
                test_counter["skipped"]["total"] += 1
                test_counter["skipped"]["names"].append(test)
                test_counter["total"] += 1
            else:
                test_counter["failed"]["total"] += 1
                test_counter["failed"]["names"].append(test)
                test_counter["total"] += 1

        print(f"\nTest Summary: {test_counter}")
        return {
            "status": "completed",
            "test_results": test_results,
            "test_counter": test_counter
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        # Clean up
        print("Cleaning up temporary directory...")
        shutil.rmtree(temp_dir)

# Process the dataset row by row
results = []
for idx, row in data.iterrows():
    if args.num_rows and idx >= args.num_rows:
        break
    print(f"Processing instance {row['instance_id']}")
    result = process_instance(row)
    results.append(result)

# Save results to a file
output_path = "results.json"
import json
with open(output_path, "w") as f:
    json.dump(results, f, indent=4)
print(f"Results saved to {output_path}")
