#!/usr/bin/python3

import json
import sys
import getopt
from datetime import datetime, timedelta, timezone

def convert_github_json_date_to_datetime(github_date_string: str):
    return datetime.strptime(github_date_string, '%Y-%m-%dT%H:%M:%SZ')

def gen_msstore_release_channel(latestgithubrelease: dict, releaselist: list) -> dict:
    channel = dict()
    channel['channel'] = 'release_ms_store'
    channel['channelConditional'] = '(WIN_PACKAGE_FULLNAME =~ "^48148WZ2100Project.Warzone2100forWindows_.*$") && (GIT_TAG =~ ".+")'
    channel['compatNotices'] = []
    return channel

def gen_release_channel(latestgithubrelease: dict) -> dict:
    channel = dict()
    channel['channel'] = 'release'
    channel['channelConditional'] = 'GIT_TAG =~ "^{0}$"'.format(latestgithubrelease['tag_name'])
    channel['compatNotices'] = []
    try:
        release = dict()
        release['propertyMatch'] = '(GIT_TAG =~ "^{0}$") && (WZ_PACKAGE_DISTRIBUTOR =~ "^wz2100.net$") && (WIN_LOADEDMODULENAMES =~ "\\"gameoverlayrenderer64.dll\\"") && ((!(FIRST_LAUNCH =~ "^2022-.+") && !(FIRST_LAUNCH =~ "^2021-.+")) || (FIRST_LAUNCH =~ "^2022-1.+") || (FIRST_LAUNCH =~ "^2022-0[4-9].+" || (FIRST_LAUNCH =~ "^2022-03-[1-3].+")))'.format(latestgithubrelease['tag_name'])
        release['id'] = 'compat-1'
        release['notification'] = { 'base': 'compatNotice', 'id': 'steam-compat-{0}'.format(latestgithubrelease['tag_name']), 'minShown': 10 }
        release['infoLink'] = 'https://wz2100.net/compat/steamoverlay/?platform={{PLATFORM}}'
        channel['compatNotices'].append(release)
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    # # Example compat notices format - NOTE: propertyMatch *MUST* be enhanced to specify the exact situation in which the notice is displayed
    # try:
    #     release = dict()
    #     release['propertyMatch'] = '(GIT_TAG =~ "^{0}$") && (WZ_PACKAGE_DISTRIBUTOR =~ "^wz2100.net$")'.format('NON-EXISTENT-TAG-MUST-BE-EDITED')
    #     release['id'] = 'compat-1'
    #     release['notification'] = { 'base': 'release_update', 'id': latestgithubrelease['tag_name'], 'minShown': 10 }
    #     release['infoLink'] = 'https://wz2100.net/?platform={{PLATFORM}}'
    #     channel['compatNotices'].append(release)
    # except KeyError as e:
    #     print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
    #     raise
    return channel

def gen_old_release_channel(latestgithubrelease: dict) -> dict:
    channel = dict()
    channel['channel'] = 'release'
    channel['channelConditional'] = 'GIT_TAG =~ ".+"'
    channel['compatNotices'] = []
    try:
        release = dict()
        release['propertyMatch'] = '(GIT_TAG =~ ".+") && (WZ_PACKAGE_DISTRIBUTOR =~ "^wz2100.net$") && (WIN_LOADEDMODULENAMES =~ "\\"gameoverlayrenderer64.dll\\"") && ((!(FIRST_LAUNCH =~ "^2022-.+") && !(FIRST_LAUNCH =~ "^2021-.+")) || (FIRST_LAUNCH =~ "^2022-1.+") || (FIRST_LAUNCH =~ "^2022-0[4-9].+" || (FIRST_LAUNCH =~ "^2022-03-[1-3].+")))'
        release['id'] = 'compat-1'
        release['notification'] = { 'base': 'compatNotice', 'id': 'steam-compat-1-{0}'.format(datetime.utcnow().strftime('%Y-%m-%d')), 'minShown': 10 }
        release['infoLink'] = 'https://wz2100.net/compat/steamoverlay/?platform={{PLATFORM}}'
        channel['compatNotices'].append(release)
    except KeyError as e:
        print("Missing expected key in latestgithubrelease JSON: {0}".format(e.args[0]))
        raise
    return channel

def gen_compat_file(latestgithubrelease: dict, releaselist: list, latestdevcommit: dict) -> dict:
    compat = dict()
    valid_thru = datetime.utcnow() + timedelta(hours=25)
    compat['validThru'] = valid_thru.replace(microsecond=0, tzinfo=timezone.utc).isoformat()
    compat['channels'] = []
    compat['channels'].append(gen_msstore_release_channel(latestgithubrelease, releaselist))
    compat['channels'].append(gen_release_channel(latestgithubrelease))
    compat['channels'].append(gen_old_release_channel(latestgithubrelease))
    return compat

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
        print ('generate_compat_json.py -r <latestrelease.json> -i <releaselist.json> -d <latestdevcommit.json>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('generate_compat_json.py -r <latestrelease.json> -i <releaselist.json> -d <latestdevcommit.json>')
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
    updates_json = gen_compat_file(latestrelease, releaselist, latestdevcommit)
    with open('compat.json', 'w', encoding='utf-8') as f:
        json.dump(updates_json, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
   main(sys.argv[1:])
