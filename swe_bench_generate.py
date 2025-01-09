from oxen import get_repo, DataFrame
import openai
import tqdm
import git
import os
import tempfile

# Retrieve the remote repository
print("Retrieving Remote Repo")
repo = get_repo("EloyMartinez/SWE-bench", host="hub.oxen.ai")

# Access the dataset
print("Accessing Remote Dataset")
dataset = DataFrame(repo, "SWE-bench_dev_with_patch_files.parquet")

# Get the size of the dataset
size = dataset.size()
print("size: ", size)

# Create OpenAI client
client = openai.Client()
model = "gpt-4o"

# Iterate over the dataset
results = dataset.list_page(1)
for result in tqdm.tqdm(results):
    print(result)
    problem_statement = result["problem_statement"]
    patch_files = result["patch_files"]  # Assuming this is a list of file paths
    repo_url = f"https://github.com/{result['repo']}"
    env_commit = result["base_commit"]
    hints_text = result["hints_text"]


    # Create a temporary directory to clone the repo
    temp_dir = tempfile.mkdtemp()

    try:
        print(f"Cloning {repo_url} into {temp_dir}")
        repo = git.Repo.clone_from(repo_url, temp_dir)

        # Checkout the base commit if it exists
        if env_commit:
            repo.git.checkout(env_commit)

        # Read the contents of the specified patch files
        file_contents = []
        for file_path in patch_files:
            full_path = os.path.join(temp_dir, file_path)
            with open(full_path, 'r') as file:
                file_contents.append(file.read())

        # Construct the context from the file contents
        context = "\n\n".join(file_contents)

        if hints_text:
            context += f"\n\nHints: {hints_text}"

        # Create the prompt with a clear objective
        prompt = (
            f"Objective: Generate a patch to fix the issue described below.\n\n"
            f"Problem Statement: {problem_statement}\n\n"
            f"Context: {context}"
        )

        # Generate the completion
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        response = completion.choices[0].message.content
        print("Assistant: " + response)

    except Exception as e:
        print(f"Error processing {result['repo']}: {e}")

    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)