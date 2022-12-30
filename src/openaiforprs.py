from dataclasses import dataclass
from typing import Optional

import git
import openai
import os
import json
import traceback
import re
import nltk
from nltk.corpus import brown

def count_words(string: str):
    # Here we are removing the spaces from start and end,
    # and breaking every word whenever we encounter a space
    # and storing them in a list. The len of the list is the
    # total count of words.
    return len(remove_emojis(string).split(" ")) + 1


def make_titlecase(string: str):
    prompt = f"Make this string Title Case and fix spelling: \"{string}\""
    try:
        result = openai.Completion.create(
            engine="text-curie-001",
            max_tokens=int(250 * 2),
            top_p=0.5,
            frequency_penalty=0.2,
            presence_penalty=1,
            prompt=prompt,
            temperature=0.24
        )

        # Print some output:
        print(prompt)
        print(result)

        return result["choices"][0]["text"].strip()
    except Exception as e:
        raise e


def remove_emojis(data):
    emoj = re.compile("["
                      u"\U0001F600-\U0001F64F"  # emoticons
                      u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                      u"\U0001F680-\U0001F6FF"  # transport & map symbols
                      u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                      u"\U00002500-\U00002BEF"  # chinese char
                      u"\U00002702-\U000027B0"
                      u"\U00002702-\U000027B0"
                      u"\U000024C2-\U0001F251"
                      u"\U0001f926-\U0001f937"
                      u"\U00010000-\U0010ffff"
                      u"\u2640-\u2642"
                      u"\u2600-\u2B55"
                      u"\u200d"
                      u"\u23cf"
                      u"\u23e9"
                      u"\u231a"
                      u"\ufe0f"  # dingbats
                      u"\u3030"
                      "]+", re.UNICODE)
    return re.sub(emoj, '', data).strip()


def has_emoji_at_start(original: str):
    original = original.strip()[0]
    modified = remove_emojis(original)
    return modified != original


def check_starts_with_verb(string: str) -> bool:
    string = remove_emojis(string)

    # A verb could be categorized to any of the following codes
    verb_codes = {
        'VB',  # Verb, base form
        'VBD',  # Verb, past tense
        'VBG',  # Verb, gerund or present participle
        'VBN',  # Verb, past participle
        'VBP',  # Verb, non-3rd person singular present
        'VBZ',  # Verb, 3rd person singular present
    }

    # tokenize the sentence
    user_provided_input_token = nltk.word_tokenize(string)
    print("The user input token: {}".format(user_provided_input_token))

    # [tag][2] the tokens
    result = nltk.pos_tag(user_provided_input_token)
    print("Result: {}".format(result))

    # only look at the first word
    first_word_result = result[0]
    print("First word result: {}".format(first_word_result))

    # get the first word's corresponding code (or tag?)
    first_word_code = first_word_result[1]
    print("First word code: {}".format(first_word_code))

    # check to see if the first word's code is contained in VERB_CODES
    if first_word_code in verb_codes:
        print("First word is a verb")
        return True
    else:
        print("First word is not a verb")
        return False

@dataclass
class PullRequestResponse:
    response_prompt: str
    invalid: bool = False
    edited: bool = False
    edited_title: Optional[str] = None
    result: Optional[str] = None


def evaluate_pr_title_for_edits(pr_title, author, commit_messages) -> PullRequestResponse:
    word_count = count_words(pr_title)
    starts_with_verb = check_starts_with_verb(pr_title)
    starts_with_emoji = has_emoji_at_start(pr_title)
    is_long_enough = word_count > 4

    response_prompt = f"In a Github format, write a comment to GitHub user \"@{author}\""

    if not (is_long_enough and starts_with_verb):

        if not is_long_enough:
            response_prompt += f" that their PR message isn't long enough"

        if not starts_with_verb:
            response_prompt += f" {'and ' if not is_long_enough else 'that their PR message'} does not start with a verb as required"

        response_prompt += '.'

        return PullRequestResponse(
            edited_title=None,
            response_prompt=response_prompt
        )

    else:  # No fatal issues so we can assume this is relatively good.

        # Let us proceed with copy editing.
        titlecase_version = make_titlecase(pr_title)

        # Check the emoji status
        if not starts_with_emoji:
            # ADD EMOJIS!! :D
            titlecase_version = emojify(titlecase_version)

        if pr_title != titlecase_version or not starts_with_emoji:
            response_prompt += f" that we have some suggested edits to their PR."

            return PullRequestResponse(
                invalid=False,
                edited=True,
                edited_title=titlecase_version,
                response_prompt=response_prompt
            )

    response_prompt += " that their PR title was perfect."

    return PullRequestResponse(
        invalid=False,
        edited=False,
        edited_title=None,
        response_prompt=response_prompt,
    )


def emojify(pr_title: str):
    prompt = f"Insert an emoji at the start of this string: "

    result = openai.Completion.create(
        engine="text-davinci-003",
        max_tokens=int(300),
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        prompt=prompt,
        suffix=f" {pr_title}",
        temperature=0
    )

    print(result)

    new_title = result["choices"][0]["text"].strip()
    emoji = new_title.replace(pr_title, '')

    # The API isn't cooperating with whitespace in the suffix so we are doing this.
    print(f"Original: {pr_title}")
    final = f"{emoji} {pr_title}"
    print(f"Final: '{final}'")

    return final


def generate_response_comment_result(pr_title, author, commit_messages, max_tokens=500) -> PullRequestResponse:
    evaluation = evaluate_pr_title_for_edits(pr_title, author, commit_messages)
    response_prompt = evaluation.response_prompt

    if evaluation.invalid:
        # We need to gin up some suggestions for the user.
        # TODO create some suggestions.
        None

    # Call the lanaguge model to do the needed bits
    result = openai.Completion.create(
        engine="text-davinci-003",
        max_tokens=int(max_tokens),
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        prompt=response_prompt,
        temperature=0.57
    )

    # Grab the result and return it
    return PullRequestResponse(
        result=result["choices"][0]["text"],
        response_prompt=response_prompt,
        edited_title=evaluation.edited_title
    )


def generate_options_prompt(pr_title, author, commit_messages, max_tokens=500):
    prompt = f"""
"""
    try:
        result = openai.Completion.create(
            engine="text-davinci-003",
            max_tokens=int(max_tokens),
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            prompt=prompt,
            temperature=0.57
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

        source_commit = repo.commit(base_sha)
        target_commit = repo.commit(head_sha)

        # Use the `git.Diff` class to get a list of modified files
        diff = source_commit.diff(target_commit)

        modified_files = []
        for d in diff:
            if d.change_type in ('A', 'M', 'T'):
                modified_files.append(d.a_path)
        return modified_files
    except git.exc.InvalidGitRepositoryError as e:
        raise ValueError("The current directory is not a Git repository.") from e


def init():
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')


def run():  # sourcery skip: avoid-builtin-shadow
    max = os.environ.get("MAX_FILES", 5)
    tokens = os.environ.get("TOKENS", 500)
    pr_title = os.environ.get("PR_TITLE")
    pr_author = os.environ.get("PR_AUTHOR")

    commit_messages = ""

    # Lets generate a response
    comment = ""
    response = None

    try:
        init()
        response = generate_response_comment_result(pr_title, pr_author, commit_messages, tokens)
        comment += response.result
        comment += f"""
<details>
  <summary>Technical Details</summary>
  
  ### Other Information
  - Title: '{pr_title}'
  - Author: '{pr_author}'
  - Commits: '{commit_messages}'
  - Edited Title: '{'None' if response is None else response.edited_title}'
  
  ### Response Prompt
  ```{'None' if response is None else response.response_prompt}```
</details>
        """
    except Exception as e:
        comment += f"""_A fault occured with the PR validation bot._
<details>
  <summary>Error Details</summary>
  
  ### Exception Information
  ```
  {traceback.format_exc()}
  ```
  ### Other Information
  - Title: '{pr_title}'
  - Author: '{pr_author}'
  - Commits: '{commit_messages}'
  - Edited Title: '{'None' if response is None else response.edited_title}'
  ### Response Prompt
  `{'None' if response is None else response.response_prompt}`
</details>
        """

    with open("comment.md", "w") as f:
        f.write(comment)


if __name__ == "__main__":
    run()
