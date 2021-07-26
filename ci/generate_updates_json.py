#!/usr/bin/python3

import json
import sys
import getopt
from datetime import datetime, timedelta, timezone

def gen_prerelease_channel(latestgithubrelease: dict, releaselist: list) -> dict:
    try:
        latest_release_id = latestgithubrelease['id']
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    # Latest Preview release (if it's newer than the latest stable release)
    latest_prerelease = {}
    prerelease_list = []
    try:
        # Find the first non-draft, prerelease
        for release in releaselist:
            if release['id'] == latest_release_id:
                break # found the latest release - stop processing
            if release['draft']:
                continue # skip draft releases
            if not release['prerelease']:
                break # found a non-draft, non-prerelease release - stop processing
            if not latest_prerelease:
                # Found first non-draft prerelease
                latest_prerelease = release
            # Found a prerelease prior to the last stable release
            prerelease_list.append(release)
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    
    if latest_prerelease and prerelease_list:
        channel = dict()
        channel['channel'] = 'prerelease'
        try:
            # build an expression that matches all prereleases since the last stable release (including the latest prerelease)
            channel['channelConditional'] = '(GIT_TAG =~ "' + ('") || (GIT_TAG =~ "'.join([release.get('tag_name') for release in prerelease_list])) + '")'
            channel['releases'] = []

            prerelease = dict()
            prerelease['buildPropertyMatch'] = '!(GIT_TAG =~ "{0}") && (PLATFORM =~ "Windows|Mac OS X|Linux|.*")'.format(latest_prerelease['tag_name'])
            prerelease['version'] = latest_prerelease['tag_name']
            prerelease['published_at'] = latest_prerelease['published_at']
            prerelease['notification'] = { 'base': 'prerelease_update', 'id': latest_prerelease['tag_name'] }
            prerelease['updateLink'] = latest_prerelease['html_url']
            channel['releases'].append(prerelease)
            return channel
        except KeyError as e:
            print("Missing expected key in releaselist JSON: {0}".format(e.args[0]))
            raise
    else:
        return None

def get_prior_stable_releases(latestgithubrelease: dict, releaselist: list) -> dict:
    try:
        latest_release_id = latestgithubrelease['id']
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    # Latest Preview release (if it's newer than the latest stable release)
    foundlatestrelease = False
    priorrelease_list = []
    try:
        # Find the first non-draft, prerelease
        for release in releaselist:
            if release['id'] == latest_release_id:
                # found the latest release
                foundlatestrelease = True
                continue
            elif foundlatestrelease:
                # Process releases after latest release
                if release['draft']:
                    continue # skip draft releases
                if release['prerelease']:
                    continue # skip prerelease releases
                # Found a prior stable release
                priorrelease_list.append(release)
    except KeyError as e:
        print("Missing expected key in releaselist JSON: {0}".format(e.args[0]))
        raise
    
    return priorrelease_list

def convert_github_json_date_to_datetime(github_date_string: str):
    return datetime.strptime(github_date_string, '%Y-%m-%dT%H:%M:%SZ')

MS_STORE_RELEASE_GRACE_DAYS = 3

def msstore_allowed_prior_stable_release(release: dict):
    release_published_at = convert_github_json_date_to_datetime(release['published_at'])
    return ((datetime.now() - release_published_at).days <= MS_STORE_RELEASE_GRACE_DAYS)

def gen_msstore_release_channel(latestgithubrelease: dict, releaselist: list) -> dict:
    channel = dict()
    channel['channel'] = 'release_ms_store'
    channel['channelConditional'] = '(WIN_PACKAGE_FULLNAME =~ "^48148WZ2100Project.Warzone2100forWindows_.*$") && (GIT_TAG =~ ".+")'
    channel['releases'] = []
    
    latest_git_tags = [latestgithubrelease['tag_name']]
    # Latest Microsoft Store release
    # NOTES:
    # - To be "correct", we'd deal with the MS Store API to verify when the latest release has gone through the process and is fully published...
    # - In lieu of that, permit all release tags published within the last 3 days or at least one prior release tag if the latest tag is not yet 3 days old
    prior_stable_releases = get_prior_stable_releases(latestgithubrelease, releaselist)
    if prior_stable_releases:
        try:
            latest_release_published_at = convert_github_json_date_to_datetime(latestgithubrelease['published_at'])
            latest_release_age_days = (datetime.now() - latest_release_published_at).days
            allowed_prior_releases_iterator = filter(msstore_allowed_prior_stable_release, prior_stable_releases)
            allowed_prior_releases = list(allowed_prior_releases_iterator)
            if (not allowed_prior_releases) and (latest_release_age_days <= MS_STORE_RELEASE_GRACE_DAYS):
                # Ensure at least one (the last) prior release is permitted when a new release is brand-new
                allowed_prior_releases.append(prior_stable_releases[0])
            for prior_release in allowed_prior_releases:
                latest_git_tags.append(prior_release['tag_name'])
        except ValueError as e:
            # Parsing the JSON dates into datetime objects likely failed
            print("Failed to extract additional previous stable releases from release info, with error: {0}".format(str(e)))
            print("Skipping this step")
    
    try:
        release = dict()
        buildPropertyMatches = []
        for git_tag in latest_git_tags:
            buildPropertyMatches.append('!(GIT_TAG =~ "^{0}$")'.format(git_tag))
        release['buildPropertyMatch'] = ' && '.join(buildPropertyMatches)
        release['version'] = latestgithubrelease['tag_name']
        release['published_at'] = latestgithubrelease['published_at']
        release['notification'] = { 'base': 'msstore_release_update', 'id': latestgithubrelease['tag_name'] }
        release['updateLink'] = 'https://data.wz2100.net/redirect/msstoreupdates.html'
        channel['releases'].append(release)
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    return channel

def gen_release_channel(latestgithubrelease: dict) -> dict:
    channel = dict()
    channel['channel'] = 'release'
    channel['channelConditional'] = 'GIT_TAG =~ ".+"'
    channel['releases'] = []
    # Latest GitHub release (for Windows, macOS, Linux)
    try:
        release = dict()
        release['buildPropertyMatch'] = '!(GIT_TAG =~ "{0}") && (PLATFORM =~ "Windows|Mac OS X|Linux|.*") && (WZ_PACKAGE_DISTRIBUTOR =~ "^wz2100.net$")'.format(latestgithubrelease['tag_name'])
        release['version'] = latestgithubrelease['tag_name']
        release['published_at'] = latestgithubrelease['published_at']
        release['notification'] = { 'base': 'release_update', 'id': latestgithubrelease['tag_name'] }
        release['updateLink'] = 'https://wz2100.net/?platform={{PLATFORM}}'
        channel['releases'].append(release)
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    # A workaround because some 4.1.0 packages shipped with an incorrect distributor
    try:
        release = dict()
        release['buildPropertyMatch'] = '(GIT_TAG =~ "^4.1.0$") && (PLATFORM =~ "Windows|Mac OS X|Linux|.*")'
        release['version'] = latestgithubrelease['tag_name']
        release['published_at'] = latestgithubrelease['published_at']
        release['notification'] = { 'base': 'release_update', 'id': latestgithubrelease['tag_name'] }
        release['updateLink'] = 'https://wz2100.net/?platform={{PLATFORM}}'
        channel['releases'].append(release)
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    return channel

def gen_development_channel(latestdevcommit: dict) -> dict:
    channel = dict()
    channel['channel'] = 'development'
    channel['channelConditional'] = '(GIT_BRANCH =~ "^master$") && !(GIT_TAG =~ ".+") && (WZ_PACKAGE_DISTRIBUTOR =~ "^wz2100.net$")'
    channel['releases'] = []
    # Latest master branch commit from GitHub
    try:
        release = dict()
        release['buildPropertyMatch'] = '!(GIT_FULL_HASH =~ "{0}")'.format(latestdevcommit['sha'])
        # construct "version" string for master branch build - "master_" + <short hash>
        short_hash = latestdevcommit['sha'][0:7]
        version_string = "master_{0}".format(short_hash)
        release['version'] = version_string
        release['published_at'] = latestdevcommit['commit']['committer']['date']
        release['notification'] = { 'base': 'dev_update', 'id': version_string }
        release['updateLink'] = 'https://github.com/Warzone2100/warzone2100/blob/master/README.md#latest-development-builds'
        channel['releases'].append(release)
    except KeyError as e:
        print("Missing expected key in latestdevcommit JSON: {0}".format(e.args[0]))
        raise
    return channel

def gen_updates_file(latestgithubrelease: dict, releaselist: list, latestdevcommit: dict) -> dict:
    updates = dict()
    valid_thru = datetime.utcnow() + timedelta(hours=25)
    updates['validThru'] = valid_thru.replace(microsecond=0, tzinfo=timezone.utc).isoformat()
    updates['channels'] = []
    prerelease_channel = gen_prerelease_channel(latestgithubrelease, releaselist)
    if not prerelease_channel is None:
        updates['channels'].append(prerelease_channel)
    updates['channels'].append(gen_msstore_release_channel(latestgithubrelease, releaselist))
    updates['channels'].append(gen_release_channel(latestgithubrelease))
    updates['channels'].append(gen_development_channel(latestdevcommit))
    return updates

def main(argv):
    latestrelease_filepath = ''
    releaselist_filepath = ''
    latestdevcommit_filepath = ''
    latestrelease = {}
    releaselist = []
    latestdevcommit = {}
    try:
        opts, args = getopt.getopt(argv,"hr:i:d:",["latestrelease=","releaselist=","latestdevcommit="])
    except getopt.GetoptError:
        print ('generate_updates_json.py -r <latestrelease.json> -i <releaselist.json> -d <latestdevcommit.json>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('generate_updates_json.py -r <latestrelease.json> -i <releaselist.json> -d <latestdevcommit.json>')
            sys.exit()
        elif opt in ("-r", "--latestrelease"):
            latestrelease_filepath = arg
        elif opt in ("-i", "--releaselist"):
            releaselist_filepath = arg
        elif opt in ("-d", "--latestdevcommit"):
            latestdevcommit_filepath = arg
    print ('latestrelease filepath file is: ', latestrelease_filepath)
    print ('releaselist filepath file is: ', releaselist_filepath)
    print ('latestdevcommit filepath file is: ', latestdevcommit_filepath)
    try:
        with open(latestrelease_filepath, 'r') as release_file, open(releaselist_filepath, 'r') as releaselist_file, open(latestdevcommit_filepath, 'r') as devcommit_file:
            latestrelease = json.load(release_file)
            releaselist = json.load(releaselist_file)
            latestdevcommit = json.load(devcommit_file)
    except FileNotFoundError as e:
        # Failed to open a file
        print("FileNotFoundError error: {0}".format(e.strerror))
        raise
    except IOError as e:
        print("Unexpected I/O error({0}): {1}".format(e.errno, e.strerror))
        raise
    updates_json = gen_updates_file(latestrelease, releaselist, latestdevcommit)
    with open('updates.json', 'w', encoding='utf-8') as f:
        json.dump(updates_json, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
   main(sys.argv[1:])
