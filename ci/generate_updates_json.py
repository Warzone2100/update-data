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

def gen_release_channel(latestgithubrelease: dict) -> dict:
    channel = dict()
    channel['channel'] = 'release'
    channel['channelConditional'] = 'GIT_TAG =~ ".+"'
    channel['releases'] = []
    # Latest GitHub release (for Windows, macOS, Linux)
    try:
        release = dict()
        release['buildPropertyMatch'] = '!(GIT_TAG =~ "{0}") && (PLATFORM =~ "Windows|Mac OS X|Linux|.*")'.format(latestgithubrelease['tag_name'])
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
