import git
import openai
import os
import json

def evaulate_pr_title(pr_title, author, commit_messages, max_tokens = 500):
    prompt = f"""
Evaluate the Pull Request Title below the three dashes ("---") to see if the Pull Request Title is compliant with all of the rules below. If the title is compliant, respond in markdown format and thank the author for picking a compliant pull request title; ignoring the template.  If the input is not compliant, respond as a GitHub comment with the template below, replacing the text in square brackets, to help the user.   When processing the template,  ignore any emoji tags in the template itself.  Assume this is the start of a conversation and none of this prompt is known to the person you are talking to.  

Rules:
1. The pull request title must be Title Case, and in the format "<EMOJI> <SHORT_DESCRIPTION>"
2. EMOJI must be an emoji OR a Github emoji tag
3. The SHORT_DESCRIPTION shall start with a verb.
4. The SHORT_DESCRIPTION should be applicable to the Commits in the input, but we should ignore this rule if the message is otherwise compliant.
5. The EMOJI should be relevant to the existing PR title, or the Commits in the input, but if the user did provide an emoji we should assume it is valid.
6. The VERB and SHORT_DESCRIPTION must form a grammatically correct phrase.
7. The SHORT_DESCIPTION should be at least 5 words.

Template:
[if the title doesn't follow the rules, tell the person why, here]

[In the options below, use the inputs to try to form a compliant message, especially the original pull request title, if possible.]

# Pick a compliant git message by clicking the applicable reaction icon below:
1. :heart: -> *[insert best option here]*
2. :horray: -> *[insert 2nd best option here]*
3. :rocket: -> *[insert 3rd option here]*
4. _OR, provide your own by editing the PR._ :eyes:

_Don't like these responses?  Downvote this comment._
---
Author: {author}
Pull Request Title: "{pr_title}"
Commits:
{commit_messages}
"""
    try:
        result = openai.Completion.create(
                    engine="text-davinci-003",
                    max_tokens=int(tokens),
                    top_p=1,
                    frequency_penalty=1,
                    presence_penalty=1,
                    prompt=prompt,
                    temperature=0.2
                    )
       
        return result["choices"][0]["text"]
    except Exception as e:
        return f"An error occurred: {e}"
    
def get_modified_files():
    try:
        with open(os.environ['GITHUB_EVENT_PATH']) as f:
            event = json.load(f)
        # Open the repository using the `git` library
        repo = git.Repo('.')

        # Get the base and head commit shas from the pull request event
        base_sha = event['pull_request']['base']['sha']
        head_sha = event['pull_request']['head']['sha']
        
        source_commit = repo.commit( base_sha )
        target_commit = repo.commit( head_sha )
              
        # Use the `git.Diff` class to get a list of modified files
        diff = source_commit.diff( target_commit )

        modified_files = []
        for d in diff:
            if d.change_type in ('A', 'M', 'T'):
                modified_files.append(d.a_path)
        return modified_files       
    except git.exc.InvalidGitRepositoryError as e:
        raise ValueError("The current directory is not a Git repository.") from e

def run():  # sourcery skip: avoid-builtin-shadow
    max = os.environ.get("MAX_FILES")
    tokens = os.environ.get("TOKENS")
    pr_title = os.environ.get("PR_TITLE")
    pr_author = os.environ.get("PR_AUTHOR")
    
    commit_messages = ""
    
    try:
        comment = evaulate_pr_title(pr_title, pr_author, commit_messages, tokens)
    except Exception as e:
        comment = f"An error occurred: {e}"
        
    with open("comment.md", "w") as f:
        f.write(comment)

if __name__ == "__main__":
    run()
