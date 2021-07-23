#!/usr/bin/python3

# NOTE: The working directory should be the checked-out `gh-pages` branch

import json
import sys
import getopt
from datetime import datetime, timedelta, timezone
from collections import namedtuple
import tarfile
import re
import urllib.request
import os
from pathlib import Path

STABLE_RELEASE_GRACE_DAYS = 2

# Modified version of urlretrieve from: https://github.com/python/cpython/blob/master/Lib/urllib/request.py
# Modified to support accepting a Request object as the url
def urlretrieve(url, filename, reporthook=None, data=None):

    import contextlib

    with contextlib.closing(urllib.request.urlopen(url, data)) as fp:
        headers = fp.info()

        tfp = open(filename, 'wb')

        with tfp:
            result = filename, headers
            bs = 1024*8
            size = -1
            read = 0
            blocknum = 0
            if "content-length" in headers:
                size = int(headers["Content-Length"])

            while True:
                block = fp.read(bs)
                if not block:
                    break
                read += len(block)
                tfp.write(block)
                blocknum += 1

    if size >= 0 and read < size:
        raise ContentTooShortError(
            "retrieval incomplete: got only %i out of %i bytes"
            % (read, size), result)

    return result

PrereleaseInfo = namedtuple('PrereleaseInfo', 'latest_prerelease prerelease_list')

def get_newer_prereleases(latestgithubrelease: dict, releaselist: list) -> dict:
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
        print("Missing expected key in releaselist JSON: {0}".format(e.args[0]))
        raise
    
    return PrereleaseInfo(latest_prerelease, prerelease_list)

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

def gen_prerelease_versionProperties(latestgithubrelease: dict, releaselist: list) -> dict:
    result = get_newer_prereleases(latestgithubrelease, releaselist)
    
    if result.latest_prerelease and result.prerelease_list:
        try:
            versionProps = dict()
            versionProps['versionStringGlob'] = result.latest_prerelease['tag_name']
            versionProps['motd'] = 'Thank you for trying a preview release of Warzone 2100!\nYour game is now hosted on the lobby server.'
            versionProps['supported'] = True
            return versionProps
        except KeyError as e:
            print("Missing expected key in releaselist JSON: {0}".format(e.args[0]))
            raise
    else:
        return None

def gen_release_versionProperties(latestgithubrelease: dict) -> dict:
    versionProps = dict()
    versionProps['versionStringGlob'] = latestgithubrelease['tag_name']
    versionProps['motd'] = 'Welcome to Warzone 2100!\nYour game is now hosted on the lobby server.'
    versionProps['supported'] = True
    return versionProps

def gen_development_versionProperties(latestdevcommit: dict) -> dict:
    versionProps = dict()
    versionProps['versionStringGlob'] = 'master *'
    versionProps['motd'] = 'Thank you for trying a development build of Warzone 2100!\nYour game is now hosted on the lobby server.'
    versionProps['supported'] = True
    return versionProps

def get_development_netcodeMinorVerArray(latestdevcommit: dict) -> dict:
    latest_vcs_commit_count = int(latestdevcommit['wz_history']['commit_count'])
    # support the last N development builds
    SUPPORTED_DEV_BUILDS_NUM = 30
    return list(str(i) for i in range(latest_vcs_commit_count - (SUPPORTED_DEV_BUILDS_NUM - 1), latest_vcs_commit_count + 1))

def create_path_for_file_if_not_exists(file_path):
    file_directory = os.path.dirname(file_path)
    Path(file_directory).mkdir(parents=True, exist_ok=True)

def get_release_source_tarball_asset(release: dict):
    for asset in release['assets']:
        if asset['name'] == 'warzone2100_src.tar.xz':
            return asset
    raise ValueError('No source tarball asset found for release: {0}'.format(release['tag_name']))        

NetcodeVer = namedtuple('NetcodeVer', 'VerMajor VerMinor')

def get_netcode_ver_from_source_tarfile(path) -> NetcodeVer:
    with tarfile.open(path) as tf:        
        print("Extracting netcode ver from files in: {0}".format(path))
        # Try the "autorevision"-generated netcode version file
        try:
            fileobj = tf.extractfile('warzone2100/lib/netplay/netplay_config.gen')
        except KeyError:
            # did not find netplay_config.gen file in archive
            fileobj = None

        if not fileobj is None:
            readfilename = 'lib/netplay/netplay_config.gen'
            netplayconfig_contents = fileobj.read().decode('utf-8', 'ignore')
            # find VERSION definitions
            result_major = re.search("static\s+uint32_t\s+NETCODE_VERSION_MAJOR\s*=\s*(\w+)\s*;", netplayconfig_contents)
            result_minor = re.search("static\s+uint32_t\s+NETCODE_VERSION_MINOR\s*=\s*(\w+)\s*;", netplayconfig_contents)
        else:
            # if that fails...
            # try the old, hard-coded info in netplay.cpp
            try:
                fileobj = tf.extractfile('warzone2100/lib/netplay/netplay.cpp')
            except KeyError:
                # did not find older netplay.cpp in archive
                raise ValueError("Source tarball did not have either expected file")
            
            readfilename = 'lib/netplay/netplay.cpp'
            netplay_contents = fileobj.read().decode('utf-8', 'ignore')
        
            # find VERSION definitions
            result_major = re.search("static\s+int\s+NETCODE_VERSION_MAJOR\s*=\s*(\w+)\s*;", netplay_contents)
            result_minor = re.search("static\s+int\s+NETCODE_VERSION_MINOR\s*=\s*(\w+)\s*;", netplay_contents)

        if (not result_major) or (not result_minor):
            print("Failed to find NETCODE_VERSION_MAJOR/MINOR in file: {0}".format(readfilename))
            raise ValueError("Failed to find NETCODE_VERSION_MAJOR/MINOR in file: {0}".format(readfilename))
    
        print(" - Found NETCODE_VERSION in: {0}".format(readfilename))
        return NetcodeVer(result_major.group(1), result_minor.group(1))

def get_netcode_ver_from_release(release: dict, github_token = None, cache_directory = '_data', temp_directory = '_tmp') -> NetcodeVer:
    # First, see if we have the information cached in the _data/ directory
    cache_file = os.path.sep.join([cache_directory, 'net_ver', release['tag_name'] + '.json'])
    create_path_for_file_if_not_exists(cache_file)
    try:
        with open(cache_file, 'r') as json_file:
            data = json.load(json_file)
            result = NetcodeVer(data['NetcodeVer']['Major'], data['NetcodeVer']['Minor'])
            print('{2}: Cached NETCODE version info - Major:{0} Minor:{1}'.format(result.VerMajor, result.VerMinor, release['tag_name']))
            return result
    except FileNotFoundError:
        # cache file doesn't exist - will fall-back below
        print('Cached information for release {0} does not exist'.format(release['tag_name']))
        pass
    except KeyError as e:
        # cache file is missing expected info - fall-back below
        print("Missing expected key in cache file: {0}".format(e.args[0]))
        pass
    except IOError as e:
        print("Unexpected I/O error({0}): {1}".format(e.errno, e.strerror))
        raise
    
    # If no usable cached info, download + extract the information from the release's source asset
    release_source_asset = get_release_source_tarball_asset(release)
    source_dl_url = release_source_asset['url']
    print('Downloading {0} source tarball: {1}'.format(release['tag_name'], source_dl_url))
    tmp_dl_file = os.path.sep.join([temp_directory, 'release', release['tag_name'], 'source.tar.xz'])
    # Download the source tarball - must provide the token
    create_path_for_file_if_not_exists(tmp_dl_file)
    url_request = urllib.request.Request(source_dl_url)
    url_request.add_header('Accept', 'application/octet-stream')
    if (not github_token is None) and github_token:
        print("Setting authorization token")
        url_request.add_unredirected_header('Authorization', 'token ' + github_token)
    urlretrieve(url_request, tmp_dl_file)
    print('Downloaded {0} source tarball: {1}'.format(release['tag_name'], source_dl_url))
    try:
        # Retrieve the NETCODE version from the appropriate file
        result = get_netcode_ver_from_source_tarfile(tmp_dl_file)
        print('{2}: Retrieved NETCODE version info - Major:{0} Minor:{1}'.format(result.VerMajor, result.VerMinor, release['tag_name']))
    except:
        os.remove(tmp_dl_file)
        raise
    os.remove(tmp_dl_file)
    
    # Cache the netcode version info
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({'NetcodeVer': {'Major': result.VerMajor, 'Minor': result.VerMinor}}, f, ensure_ascii=False, indent=2)
    
    return result

def convert_github_json_date_to_datetime(github_date_string: str):
    return datetime.strptime(github_date_string, '%Y-%m-%dT%H:%M:%SZ')

def allowed_prior_stable_release(release: dict):
    release_published_at = convert_github_json_date_to_datetime(release['published_at'])
    return ((datetime.now() - release_published_at).days <= STABLE_RELEASE_GRACE_DAYS)

def get_releases_netcodeVersions(latestgithubrelease: dict, releaselist: list) -> list:
    github_token = os.getenv("GITHUB_TOKEN", default=None)
    
    versions = []
    
    try:
        latest_release_published_at = convert_github_json_date_to_datetime(latestgithubrelease['published_at'])
        if (datetime.now() - latest_release_published_at).days <= STABLE_RELEASE_GRACE_DAYS:
            allowed_prior_releases = []
            # Also permit at least one prior release, since the new release is brand-new (and any stable releases within past STABLE_RELEASE_GRACE_DAYS days)
            prior_stable_releases = get_prior_stable_releases(latestgithubrelease, releaselist)
            if prior_stable_releases:
                allowed_prior_releases_iterator = filter(allowed_prior_stable_release, prior_stable_releases)
                allowed_prior_releases = list(allowed_prior_releases_iterator)
                if not allowed_prior_releases:
                    # Ensure at least one (the last) prior release is permitted when a new release is brand-new
                    allowed_prior_releases.append(prior_stable_releases[0])
            for prior_release in allowed_prior_releases:
                versions.append(get_netcode_ver_from_release(prior_release, github_token))
    except ValueError as e:
        # Parsing the JSON dates into datetime objects likely failed
        print("Failed to extract additional previous stable releases from release info, with error: {0}".format(str(e)))
        print("Skipping this step")
    
    versions.append(get_netcode_ver_from_release(latestgithubrelease, github_token))
    
    result = get_newer_prereleases(latestgithubrelease, releaselist)
    if result.latest_prerelease:
        versions.append(get_netcode_ver_from_release(result.latest_prerelease, github_token))
    
    return versions

def gen_lobby_file(latestgithubrelease: dict, releaselist: list, latestdevcommit: dict) -> dict:
    lobbyinfo = dict()
    lobbyinfo['listMOTD_Default'] = 'Welcome! The latest version of Warzone 2100 is {0}\nDownload @ https://wz2100.net'.format(latestgithubrelease['tag_name'])
    lobbyinfo['listMOTD_LastHostedGame'] = 'Download {0} - 3.1.5 & 3.2.3 are unsupported!'.format(latestgithubrelease['tag_name'])
    lobbyinfo['unsupportedHostMessage'] = 'Your version of the game is not supported any longer.\n Update your game version today @ https://wz2100.net !'
    
    lobbyinfo['versionProperties'] = []
    prerelease_versionProperties = gen_prerelease_versionProperties(latestgithubrelease, releaselist)
    if not prerelease_versionProperties is None:
        lobbyinfo['versionProperties'].append(prerelease_versionProperties)
    lobbyinfo['versionProperties'].append(gen_release_versionProperties(latestgithubrelease))
    lobbyinfo['versionProperties'].append(gen_development_versionProperties(latestdevcommit))
    lobbyinfo['versionProperties'].append({ 'versionStringGlob': '*', 'motd': 'Please upgrade your Warzone to {0}! Your version is NOT supported.\nSee: https://wz2100.net'.format(latestgithubrelease['tag_name']), 'supported': False })
    
    lobbyinfo['supportedNetcodeVerMajorMinor'] = {}
    
    def addSupportedNetcodeVer(VerMajor, VerMinor = None):
        nonlocal lobbyinfo
        if VerMajor in lobbyinfo['supportedNetcodeVerMajorMinor']:
            if not VerMinor is None:
                lobbyinfo['supportedNetcodeVerMajorMinor'][VerMajor].append(VerMinor)
        else:
            MinorVers = []
            if not VerMinor is None:
                MinorVers.append(VerMinor)
            lobbyinfo['supportedNetcodeVerMajorMinor'][VerMajor] = MinorVers
    
    # older master branch builds, custom forks, anything built from a non-master branch
    addSupportedNetcodeVer('0x1000')
    # master branch (development builds)
    lobbyinfo['supportedNetcodeVerMajorMinor']['0x10a0'] = get_development_netcodeMinorVerArray(latestdevcommit)
    # latest release + latest pre-release
    release_versions = get_releases_netcodeVersions(latestgithubrelease, releaselist)
    for version in release_versions:
        addSupportedNetcodeVer(version.VerMajor, version.VerMinor)
    
    return lobbyinfo

def main(argv):
    latestrelease_filepath = ''
    releaselist_filepath = ''
    latestdevcommit_filepath = ''
    output_filepath = ''
    latestrelease = {}
    releaselist = []
    latestdevcommit = {}
    try:
        opts, args = getopt.getopt(argv,"hr:i:d:o:",["latestrelease=","releaselist=","latestdevcommit=","output="])
    except getopt.GetoptError:
        print ('generate_lobby_json.py -r <latestrelease.json> -i <releaselist.json> -d <latestdevcommit.json> -o <outputfile.json>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('generate_lobby_json.py -r <latestrelease.json> -i <releaselist.json> -d <latestdevcommit.json> -o <outputfile.json>')
            sys.exit()
        elif opt in ("-r", "--latestrelease"):
            latestrelease_filepath = arg
        elif opt in ("-i", "--releaselist"):
            releaselist_filepath = arg
        elif opt in ("-d", "--latestdevcommit"):
            latestdevcommit_filepath = arg
        elif opt in ("-o", "--output"):
            output_filepath = arg
    print ('latestrelease filepath file is: ', latestrelease_filepath)
    print ('releaselist filepath file is: ', releaselist_filepath)
    print ('latestdevcommit filepath file is: ', latestdevcommit_filepath)
    print ('output_filepath is: ', output_filepath)
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
    lobby_json = gen_lobby_file(latestrelease, releaselist, latestdevcommit)
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(lobby_json, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
   main(sys.argv[1:])
