from flask import current_app
from flask import request
import sys
import os
import json
from client import client
import requests
import math
import tweepy

class NoSuchLibrary(Exception):
    pass

def get_data(yrange):
    # Get the information from Solr
    # The specification of the year range is just to prevent older material
    # to be included if that happens to get loaded
    query = current_app.config.get('QUERY') + " year:%s" % yrange
    params = {'wt': 'json',
               'q': current_app.config.get('QUERY'),
              'fl': current_app.config.get('FIELDS'),
              'sort': 'citation_count_norm desc',
              'rows': current_app.config.get('MAX_HITS')}
    response = client().get(current_app.config.get('SOLR_PATH'), params=params)
    if response.status_code != 200:
        return {"Error": "Unable to get results!",
                "Error Info": response.text,
                "Status Code": response.status_code}
    resp = response.json()
    # Collect meta data
    return resp['response']['docs']

def get_library_id(token, libname):
    library_url = "%s/libraries" % (current_app.config.get('LIBRARY_PATH'))
    response = client().get(library_url)
    data = response.json()['libraries']
    try:
        libdata = [d for d in data if d['name'] == libname][0]
    except:
        # We did not find a library with this name, even though it was initially found and added to "goodlibs"
        # This should never happen!
        raise NoSuchLibrary
    return libdata['id']

def get_library(token, libid, rows=100, start=0, with_metadata=False):
    # Retrieve the contents of the library specified
    # rows: the number of records to retrieve per call (in general, we cannot retrieve everything in one call)
    params = {
        'rows': rows,
        'start': start,
        'fl': 'bibcode,title,first_author_norm, author_count'
    }
    library_url = "%s/libraries/%s" % (current_app.config.get('LIBRARY_PATH'), libid)
    response = client().get(library_url, params=params)
    data = response.json()
    # The metadata in the header tells us how many records this library contains
    num_documents = data['metadata']['num_documents']
    # Get the results contained in this first request
    try:
        documents = data['solr']['response']['docs']
    except:
        raise TypeError
    # The number of rows in the requests and the number of records in the library specifies how often to paginate
    num_paginates = int(math.ceil((num_documents) / (1.0*rows)))
    # Update the start position with the number of records we have retrieved so far
    start += rows
    # Start retrieving the remainder of the contents
    for i in range(num_paginates):
        params['start'] = start
        response = client().get(library_url, params=params)
        data = response.json()
        # Add the bibcodes from this batch to the collection
        documents.extend(data['solr']['response']['docs'])
        # Update the start position for the next batch
        start += rows
    if not with_metadata:
        return [d['bibcode'] for d in documents]
    else:
        return documents

def update_library(token, bibcodes, libid, action='add'):
    library_url = "%s/documents/%s" % (current_app.config.get('LIBRARY_PATH'), libid)
    # Create the library with the first list of bibcodes (may be the only)
    params = {
        'name': 'Current ADS Article of the Day batch',
        'description': 'Current ADS Article of the Day batch',
        'public': True,
        'action': action,
        'bibcode': bibcodes
    }
    headers = {
        'Content-type': 'application/json',
        'Accept': 'text/plain',
    }
    response = client().post(library_url, data=json.dumps(params), headers=headers)
    return response.json()

def cleanup_data(data):
    api_token = current_app.config.get('API_TOKEN')
    library_name= current_app.config.get('AOD_LIBRARY_NAME')
    try:
        library_id = get_library_id(api_token, library_name)
    except:
        sys.exit('Unable to find library ID for "%s"' % library_name)
    # Get the bibcodes of all articles posted earlier as ADS Article of the Day
    prior_articles = get_library(api_token, library_id)
    # Remove these from the current set (if present)
    data = [d for d in data if d['bibcode'] not in prior_articles]
    return data

def save_new_batch(batch):
    bibcodes = [e[1] for e in batch]
    api_token = current_app.config.get('API_TOKEN')
    library_name= current_app.config.get('BATCH_LIBRARY_NAME')
    try:
        library_id = get_library_id(api_token, library_name)
    except:
        raise Exception('Unable to find library ID for "%s"' % library_name)
    res = update_library(api_token, bibcodes, library_id)
    res['library_url'] = "%s/%s" % (current_app.config.get('ADS_LIBRARY_PATH'), library_id)
    return res

def post_to_slack(slack_data):
    url = current_app.config.get('SLACK_END_POINT')
    response = requests.post(
        url, 
        data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code != 200:
        raise ValueError(
            'Request to slack returned an error %s, the response is:\n%s'
            % (response.status_code, response.text)
        )
    return 'success'

def retrieve_article():
    # Get articles in the current batch
    api_token = current_app.config.get('API_TOKEN')
    library_name= current_app.config.get('BATCH_LIBRARY_NAME')
    try:
        library_id = get_library_id(api_token, library_name)
    except:
        raise Exception('Unable to find library ID for "%s"' % library_name)
    # Get the articles from the current batch (contents of the batch library)
    batch_articles = get_library(api_token, library_id, with_metadata=True)
    # Select the Article of the Day (the first one in the batch)
    article = batch_articles[0]
    # Remove this article from the batch library
    bibcodes = [article['bibcode']]
    res = update_library(api_token, bibcodes, library_id, action='remove')
    # Check whether a record was actually removed from the library
    try:
        number_removed = res['number_removed']
    except:
        number_removed = 0
    if number_removed != 1:
        raise Exception('Failed to remove %s from batch library' % article['bibcode'])
    # We have an article of the day
    return article

def post_to_twitter(art_data):
    # Get some essentials for posting
    tag = current_app.config.get('TWITTER_TAG')
    consumer_key = current_app.config.get('TWITTER_CONSUMER_KEY')
    consumer_secret = current_app.config.get('TWITTER_CONSUMER_SECRET')
    access_key = current_app.config.get('TWITTER_ACCESS_KEY')
    access_secret = current_app.config.get('TWITTER_ACCESS_SECRET')
    max_post_length = current_app.config.get('TWITTER_POST_LENGTH')
    max_url_length = current_app.config.get('TWITTER_URL_LENGTH')
    # Prepare the post
    # We include a URL to the abstract
    url  = "%s/%s/abstract" % (current_app.config.get('ABSTRACT_PATH'), art_data['bibcode'])
    # With a single author we do not include "et al"
    nauthors = art_data.get('author_count',1)
    etal = ''
    if nauthors > 1:
        etal = " et al"
    # The message body consists of the first author and the title (cropped if necessary)
    body = "%s%s: %s" % (art_data['first_author_norm'], etal, art_data['title'][0])
    trailer = " %s %s" % (url,tag)
    # Determine if we need to crop the message body
    if len(body) + max_url_length + len(tag) < max_post_length:
        post = "%s%s" % (body, trailer)
    else:
        body_length = len(body) - (max_url_length + len(tag))
        post = "%s[...]%s" % (body[:body_length],trailer)
    # Authenticate to be able to do the post
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_key, access_secret)
    api = tweepy.API(auth)
    # Do the post
    status = api.update_status(post)
    return status
        
    