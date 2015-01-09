#!/usr/bin/env python3
# -*- coding: utf-8 -*-


""" A Git pre-commit hook written in Python to manage multiple Git
    user identities.
"""


# ..................................................................... Imports
import configparser
import os.path
import subprocess
import sys
import textwrap
import time
import urllib.parse


# ............................................................ Config functions
def config_create(filename):
    """ Create a configuration file containing sample data inside the home
        directory if none exists yet.

        Args:
            filename (str): The complete `filepath` of the configuration file
    """
    preset = configparser.ConfigParser()

    preset["General"] = {}
    preset["General"]["enable_hook"] = "True"
    preset["General"]["sleep_duration"] = "1.5"

    preset["Passport 0"] = {}
    preset["Passport 0"]["email"] = "email_0@example.com"
    preset["Passport 0"]["name"] = "name_0"
    preset["Passport 0"]["service"] = "github.com"

    preset["Passport 1"] = {}
    preset["Passport 1"]["email"] = "email_1@example.com"
    preset["Passport 1"]["name"] = "name_1"
    preset["Passport 1"]["service"] = "gitlab.com"

    if not os.path.exists(filename):
        try:
            msg = """
                No configuration file found.
                Generating a sample configuration file.
            """

            print(textwrap.dedent(msg).strip())
            with open(filename, "w") as configfile:
                preset.write(configfile)
            sys.exit("\n~Done~")

        except Exception as error:
            print(error)
            raise sys.exit("\n~Quitting~")


def config_read(filename):
    """ Read a provided configuration file and «import» allowed sections and
        their keys/values into a dictionary.

        Args:
            filename (str): The complete `filepath` of the configuration file

        Returns:
            config (dict): Contains all allowed configuration sections
    """
    data = configparser.ConfigParser()
    data.read(filename)

    # Match an arbitrary number of sections starting with pattern
    pattern = "Passport"

    # A generator to filter matching sections:
    # Let's see if user defined config sections match a pattern
    def generate_matches():
        for section in data.items():
            if pattern in section[0]:
                yield dict(section[1])

    # Construct a custom dict containing allowed sections
    config = dict(data.items("General"))
    config["git_local_id"] = dict(enumerate(generate_matches()))

    return config


def config_validate(config):
    """ Validate and convert certain keys and values of a given dictionary
        containing a set of configuration options. If unexpected values are
        found we quit the script and notify the user what went wrong.

        Since ``ConfigParser`` only accepts strings when setting up a default
        config it is necessary to convert some values to numbers and boolean.

        Args:
            config (dict): Contains all allowed configuration sections

        Returns:
            config (dict): Contains valid and converted configuration options
    """
    for key, value in config.items():
        if key == "enable_hook":
            if value == "True":
                config[key] = True
            elif value == "False":
                config[key] = False
            else:
                msg = "E > Settings > %s: Expecting True or False." % (key)
                raise sys.exit(msg)

        elif key == "sleep_duration":
            try:
                config[key] = float(value)
            except ValueError:
                msg = "E > Settings > %s: Expecting float or number." % (key)
                raise sys.exit(msg)

        # Here the values could really be anything...
        elif key == "git_local_id":
            pass

        else:
            msg = "E > Settings > %s: Section/key unknown." % (key)
            raise sys.exit(msg)

    return config


# ............................................................... Git functions
def git_get_id(config, scope, property):
    """ Get the email address or username of the global or local Git ID.

        Args:
            config (dict): Contains validated configuration options
            scope (str): Search inside a `global` or `local` scope
            property (str): Type of `email` or `name`

        Returns:
            git_id (str): A name or email address
            error (str): Exception
    """
    try:
        git_process = subprocess.Popen([
            "git",
            "config",
            "--get",
            "--" + scope,
            "user." + property
        ], stdout=subprocess.PIPE)

        git_id = git_process.communicate()[0].decode("utf-8")
        return git_id.replace("\n", "")

    except Exception as error:
        raise error


def git_get_url():
    """ Get the local remote.origin.url of a Git repository.

        Returns:
            git_url (str): The local and active remote.origin.url
            error (str): Exception
    """
    try:
        git_process = subprocess.Popen([
            "git",
            "config",
            "--get",
            "--local",
            "remote.origin.url"
        ], stdout=subprocess.PIPE)

        git_url = git_process.communicate()[0].decode("utf-8")
        return git_url.replace("\n", "")

    except Exception as error:
        raise error


def git_set_id(config, data, property):
    """ Set the email address or username as a local Git ID for a repository.

        Args:
            config (dict): Contains validated configuration options
            data (str): A name or email address
            property (str): Type of `email` or `name`

        Returns:
            error (str): Exception
    """
    try:
        subprocess.Popen([
            "git",
            "config",
            "--local",
            "user." + property,
            data
        ], stdout=subprocess.PIPE)

    except Exception as error:
        raise error


# ............................................................ Helper functions
def get_user_input(pool):
    """ Prompt a user to select a number from a list of numbers representing
        available Git IDs. Optionally the user can choose `q` to quit the
        selection process.

        Args:
            pool (list): A list of numbers representing available Git IDs

        Returns:
            selection (int): A number representing a Git ID chosen by a user
    """
    while True:
        # http://stackoverflow.com/questions/7437261/how-is-it-possible-to-use-raw-input-in-a-python-git-hook
        sys.stdin = open("/dev/tty")
        selection = input("» Select a passport [ID] or «(q)uit»: ")

        try:
            selection = int(selection)
        except ValueError:
            if selection == "q" or selection == "quit":
                sys.exit("\n~Quitting~\n")
            continue

        if selection not in pool:
            continue
        break
    return selection


def print_choice(choice):
    """ Before showing the actual prompt by calling `get_user_input()` print a
        list of available Git IDs containing properties ID, «scope», name,
        email and service.

        Args:
            choice (dict): Contains a list of preselected Git ID candidates
    """
    for key, value in choice.items():
        if value.get("flag") == "global":
            msg = """
                ~:Global ID: [%s]
                    . User: %s
                    . Mail: %s
            """
            print(textwrap.dedent(msg).lstrip() % (
                key,
                value["name"],
                value["email"])
            )
        else:
            msg = """
                ~Passport ID: [%s]
                    . User: %s
                    . Mail: %s
                    . Service: %s
            """
            print(textwrap.dedent(msg).lstrip() % (
                key,
                value["name"],
                value["email"],
                value["service"])
            )


def add_global_id(config, target):
    """ Adds the global Git ID to a dictionary containing potential preselected
        candidates.

        Args:
            config (dict): Contains validated configuration options
            target (dict): Contains preselected local Git IDs
    """
    global_email = git_get_id(config, "global", "email")
    global_name = git_get_id(config, "global", "name")
    local_id = config["git_local_id"]

    if global_email and global_name:
        position = len(local_id)
        target[position] = {}
        target[position]["email"] = global_email
        target[position]["name"] = global_name
        target[position]["flag"] = "global"


# .............................................................. Implementation
def identity_exists(config, email, name, url):
    """ Prints an existing ID of a local gitconfig.

        Args:
            config (dict): Contains validated configuration options
            email (str): An email address
            name (str): A name
            url (str): A remote.origin.url
    """
    duration = config["sleep_duration"]

    if not url:
        url = "«remote.origin.url» is not set."

    msg = """
        ~Intermission~

        ~Active Passport:
            . User: %s
            . Mail: %s
            . Remote: %s
    """
    print(textwrap.dedent(msg).lstrip() % (name, email, url))
    sys.exit(time.sleep(duration))


def url_exists(config, url):
    """ If a local gitconfig contains a remote.origin.url add all user defined
        Git IDs matching remote.origin.url as a candidate. However if there is
        not a single match then add all available user defined Git IDs and the
        global Git ID as candidates.

        Args:
            config (dict): Contains validated configuration options
            url (str): A remote.origin.url

        Returns:
            candidates (dict): Contains preselected Git ID candidates
    """
    local_id = config["git_local_id"]
    netloc = urllib.parse.urlparse(url)[1]

    # A generator to filter matching sections:
    # Let's see if user defined IDs match remote.origin.url
    def generate_candidates():
        for key, value in local_id.items():
            if value.get("service") == netloc:
                yield (key, value)

    candidates = dict(generate_candidates())

    if len(candidates) >= 1:
        msg = """
            ~Intermission~
                One or more identities match your current git provider.
                remote.origin.url: %s
        """
        print(textwrap.dedent(msg).lstrip() % (url))
    else:
        candidates = local_id
        msg = """
            ~Intermission~
                Zero passports matching - listing all passports.
                remote.origin.url: %s
        """

        print(textwrap.dedent(msg).lstrip() % (url))
        add_global_id(config, candidates)

    print_choice(candidates)
    return candidates


def no_url_exists(config, url):
    """ If a local gitconfig does not contain a remote.origin.url add
        all available user defined Git IDs and the global Git ID as
        candidates.

        Args:
            config (dict): Contains validated configuration options
            url (str): A remote.origin.url

        Returns:
            candidates (dict): Contains preselected Git ID candidates
    """
    candidates = config["git_local_id"]
    msg = """
        ~Intermission~
            «remote.origin.url» is not set, listing all IDs:
    """

    add_global_id(config, candidates)
    print(textwrap.dedent(msg).lstrip())
    print_choice(candidates)
    return candidates


# ........................................................................ Glue
def main():
    config_file = os.path.expanduser("~/.git_passport")
    config_create(config_file)

    config = config_validate(config_read(config_file))

    if config["enable_hook"]:
        local_email = git_get_id(config, "local", "email")
        local_name = git_get_id(config, "local", "name")
        local_url = git_get_url()

        if local_email and local_name:
            identity_exists(config, local_email, local_name, local_url)
        elif local_url:
            candidates = url_exists(config, local_url)
        else:
            candidates = no_url_exists(config, local_url)

        selected_id = get_user_input(candidates.keys())
        git_set_id(config, candidates[selected_id]["email"], "email")
        git_set_id(config, candidates[selected_id]["name"], "name")
        print("\n~Done~\n")


if __name__ == "__main__":
    main()
