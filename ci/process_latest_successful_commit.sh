#!/bin/bash
#
# Expects the following environment variables to be set:
# GITHUB_REPOSITORY = "org/repo"
# BRANCH = "master"
# GITHUB_TOKEN

if [ -z "${GITHUB_REPOSITORY}" ]; then
  echo "- GITHUB_REPOSITORY environment variable is not set"
  exit 1
fi

if [ -z "${BRANCH}" ]; then
  echo "- BRANCH environment variable is not set"
  exit 1
fi

if [ -z "${GITHUB_TOKEN}" ]; then
  echo "- GITHUB_TOKEN environment variable is not set"
  exit 1
fi

PAGE=1
LATEST_COMMIT_SHA_THAT_PASSED_CHECKS=""
LATEST_COMMIT_PUBLISHED_DATE=""
LATEST_COMMIT_FULL_DATA=""

while [ $PAGE -le 5 ]; do
  
  PAGE_QUERY=""
  if [ "${PAGE}" -gt "1" ]; then
    PAGE_QUERY="&page=${PAGE}"
  fi
  
  echo "----------"
  echo "Fetching page ${PAGE} of commits for ${BRANCH} branch of: ${GITHUB_REPOSITORY}"
  COMMITS_DATA=$(curl -H "Authorization: token ${GITHUB_TOKEN}" -s "https://api.github.com/repos/${GITHUB_REPOSITORY}/commits?sha=${BRANCH}${PAGE_QUERY}")
  COMMIT_SHA_LIST=$(echo "${COMMITS_DATA}" | jq --raw-output '.[] | .sha')

  while IFS= read -r commit_sha; do
    echo "- Processing: ${commit_sha}"
  
    FILTERED_SLUGS='["cirrus-ci","travis-ci"]'
    DESIRED_SLUGS='["github-actions"]'
  
    # Get list of check runs for the commit
    CHECK_RUNS=$(curl -H "Authorization: token ${GITHUB_TOKEN}" -H "Accept: application/vnd.github.antiope-preview+json" -s \
        "https://api.github.com/repos/${GITHUB_REPOSITORY}/commits/${commit_sha}/check-runs")
  
    # Verify that this contains check runs
    CHECK_COUNT=$(echo "${CHECK_RUNS}" | jq --raw-output '.total_count')
    case $CHECK_COUNT in
        ''|*[!0-9]*) continue;;
        *) ## do nothing
        ;;
    esac
    if [ ! "${CHECK_COUNT}" -gt "1" ]; then
      echo "  - Commit did not return any check runs - skipping"
      continue
    fi
  
    # Getting a list of check runs for a commit that have completed and were successful
    SUCCESSFUL_CHECK_RUNS=$(echo "${CHECK_RUNS}" | \
      jq --argjson filtered_slugs ''"${FILTERED_SLUGS}"'' \
      '[.check_runs[] | {status: .status, conclusion: .conclusion, name: .name, check_suite: .check_suite, app: {slug: .app.slug, owner: {login: .app.owner.login, id: .app.owner.id }}} | select( .app.slug as $slug | $filtered_slugs | index($slug) == null ) | select ( .status == "completed" and .conclusion == "success" )]')
  
    # If the output is empty, the check runs are not yet finished (or failed to finish successfully)
    if [ -z "${SUCCESSFUL_CHECK_RUNS}" ]; then
      echo "  - Commit seems to have no successful check runs (yet?)"
      continue
    fi
  
    # Verify that some checks with specified slugs have completed
    NUM_DESIRED_CHECK_RUNS=$(echo "${SUCCESSFUL_CHECK_RUNS}" | \
      jq --raw-output --argjson desired_slugs ''"${DESIRED_SLUGS}"'' \
      '[.[] | select( .app.slug as $slug | $desired_slugs | index($slug) )] | length')
    case $NUM_DESIRED_CHECK_RUNS in
        ''|*[!0-9]*) continue;;
        *) ## do nothing
        ;;
    esac
    if [ "${NUM_DESIRED_CHECK_RUNS}" -gt "1" ]; then
      echo "  - Desired check runs that have completed successfully: ${NUM_DESIRED_CHECK_RUNS}"
      LATEST_COMMIT_SHA_THAT_PASSED_CHECKS="${commit_sha}"
      LATEST_COMMIT_PUBLISHED_DATE="$(echo "${COMMITS_DATA}" | jq --raw-output '.[] | select(.sha=="'"${commit_sha}"'") | .commit.committer.date')"
      LATEST_COMMIT_FULL_DATA="$(echo "${COMMITS_DATA}" | jq '.[] | select(.sha=="'"${commit_sha}"'")')"
      break 2
    fi
  
  done < <( echo "${COMMIT_SHA_LIST}" )

  if [ ! -z "${LATEST_COMMIT_SHA_THAT_PASSED_CHECKS}" ]; then
    echo "  - Found commit: ${LATEST_COMMIT_SHA_THAT_PASSED_CHECKS}"
    break
  fi
  
  PAGE=$(( $PAGE + 1 ))
done

if [ -z "${LATEST_COMMIT_SHA_THAT_PASSED_CHECKS}" ]; then
  echo "- Unable to find commit that has passed checks"
  exit 1
fi

echo "Latest commit that has passed checks: ${LATEST_COMMIT_SHA_THAT_PASSED_CHECKS}"
COMMIT_SHORT_HASH="$(echo "${LATEST_COMMIT_SHA_THAT_PASSED_CHECKS}" | head -c 7)"
MASTER_VERSION="master_${COMMIT_SHORT_HASH}"

# Write out ${LATEST_COMMIT_FULL_DATA}
echo "${LATEST_COMMIT_FULL_DATA}" > "latest_successful_commit_tmp.json"

# Now get some additional data:
LATEST_COMMIT_NODE_ID="$(echo "${LATEST_COMMIT_FULL_DATA}" | jq --raw-output '.node_id')"
echo "LATEST_COMMIT_NODE_ID=${LATEST_COMMIT_NODE_ID}"
NODE_INFO="$(curl -H "Authorization: bearer ${GITHUB_TOKEN}" -X POST -d " \
 { \
   \"query\": \"{ node(id: \\\"${LATEST_COMMIT_NODE_ID}\\\") { ... on Commit { id, oid, url, history(first: 0) { totalCount } } } }\" \
 } \
" -s "https://api.github.com/graphql")"
LATEST_COMMIT_COUNT="$(echo "${NODE_INFO}" | jq --raw-output '.data.node.history.totalCount')"
echo "LATEST_COMMIT_COUNT=${LATEST_COMMIT_COUNT}"
echo "{ \"wz_history\": { \"commit_count\": \"${LATEST_COMMIT_COUNT}\" } }" > "additional_commit_data.json"
jq -s '.[0] * .[1]' "latest_successful_commit_tmp.json" "additional_commit_data.json" > "latest_successful_commit.json"
