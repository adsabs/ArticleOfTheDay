import os
import sys
import math
from datetime import datetime
from collections import defaultdict
from random import sample
from flask import current_app, request
from utils import get_data
from utils import cleanup_data
from utils import save_new_batch
from utils import retrieve_article
from utils import post_to_slack
from utils import post_to_twitter
from utils import update_main_library
import paper_network

def generate_batch():
    # Initialize data structures
    ## The current date
    current_date = datetime.now()
    ## The dictionary that will hold the bibcodes in each cluster
    cluster_members = defaultdict(list)
    ## The dictionary that contains the label for each cluster
    cluster_labels = {}
    ## The dictionary that contains the necessary metadata for each bibcode
    graph = {}
    ## The list that will hold the candidates for the new batch
    candidates = []
    ## bibstems list to avoid papers from the same journal
    bibstems = []
    # Retrieve the initial metadata from Solr (specify a year range)
    # Include the previous year in January
    if current_date.month = 1:
        year_range = "%s-%s" % (current_date.year - 1, current_date.year)
    else:
        year_range = str(current_date.year)
    data = get_data(year_range)
    # From the initial dataset, get the actual candidates by
    # 1. removing all publications that we used previously
    clean_data = cleanup_data(data)
    # Create a paper network based on the candidates found
    # This network will be segmented into clusters. These clusters will be used to find candidates.
    visdata = paper_network.get_papernetwork(clean_data, current_app.config.get("MAX_GROUPS"))
    # Use the network to determine the new batch. The clustering is stored in the
    # "summaryGraph" attribute, while the complete network in stored in "fullGraph".
    #
    # For each cluster, retrieve the keywords that describe its contents.
    # It is possible not enough information is available to retrieve keywords
    for summary_node in visdata['summaryGraph']['nodes']:
        cluster_labels[summary_node['node_name']] = list(summary_node['node_label'].keys())
    # Every node in the complete network represents a publication. The node name is the bibcode
    # of the publication. The weight of the node within the network is determined from its
    # indegree (number of citations), the number of authors and the 90-day reads. The weight
    # closely resembles the "classic factor".
    for node in visdata['fullGraph']['nodes']:
        autnum = max(node['author_count'], 1)
        citnum = node['citation_count']
        rdsnum = node['read_count']
        try:
            weight = math.log10(1+(float(citnum + rdsnum)/float(autnum)))
        except:
            weight = float(node['cite_read_boost'])
        cluster_members[node['group']].append((node['node_name'], weight))
        # Here we store all attributes of each node to be accessed later on
        graph[node['node_name']] = node
    # Now we cycle through the clusters and build a list of candidates
    for cluster,bibset in cluster_members.items():
        candidate = bibset[0][0]
        # we do a minimal effort to try to avoid multiple candidates from 1 journal
        if candidate[4:9] in bibstems:
            candidate = bibset[1][0]        
        candidates.append((cluster, candidate))
        bibstems.append(candidate[4:9])
    # The new batch is a random pick of 5 from the candidates
    new_batch = sample(candidates, 5)
    # If the new batch has less than 5 articles, sound the alarm
    if len(new_batch) < 5:
        error_message = {
            'text': '@edwin Found only %s articles instead of 5! Check!' % len(new_batch),
            'link_names': 1
        }
        try:
            res = post_to_slack(error_message)
        except:
            res = 'failed'
        sys.exit('AoD batch is too small. Post to Slack: %s' % res)
    # Store the new batch in the appropriate ADS Library
    try:
        saved_batch = save_new_batch(new_batch)
    except Exception as err:
        error_message = {
            'text': '@edwin Something went wrong saving the current AoD batch:\n%s'%err,
            'link_names': 1
        }
        try:
            res = post_to_slack(error_message)
        except:
            res = 'failed'
        sys.exit('Something went wrong saving the current AoD batch. Post to Slack: %s' % res)        
    # Check that 5 records were posted
    try:
        number_added = saved_batch['number_added']
    except:
        number_added = 0
    if number_added != 5:
        error_message = {
            'text': '@edwin Something went wrong saving the current AoD batch! Please check!',
            'link_names': 1
        }
        try:
            res = post_to_slack(error_message)
        except:
            res = 'failed'
        sys.exit('Something went wrong saving the current AoD batch. Post to Slack: %s' % res)
    # Email the overview of the new batch. 
    # For each candidate, include the keywords of the cluster it came from
    subject = '<%s|Articles of the Day - batch %s/%s/%s>' % (saved_batch['library_url'], current_date.month, current_date.day,current_date.year)
    message = '```'
    for entry in new_batch:
        try:
            label = "; ".join([l.decode("utf-8") for l in cluster_labels[entry[0]]])
        except:
            label = "NA"
        message += "%s\tlabel: %s\n"%(entry[1],label)
    message += '```'
    post_message = {
        'text': '@edwin %s\nEntries:\n%s' % (subject, message),
        'link_names': 1
    }
    try:
        res = post_to_slack(post_message)
    except:
        res = 'failed'
        sys.stderr.write('Something went wrong posting the current AoD batch to Slack.')

def post_article():
    # Get one article from the current batch
    try:
        article_of_the_day = retrieve_article()
    except Exception as err:
        error_message = {
            'text': '@edwin Something went wrong retrieving the Article of the Day:\n%s'%err,
            'link_names': 1
        }
        try:
            res = post_to_slack(error_message)
        except:
            res = 'failed'
        sys.exit('Something went wrong retrieving the Article of the Day. Post to Slack: %s' % res)
    # Now we can start posting the article
    # 1. post to Twitter
    error_message = {}
    try:
        twitter = post_to_twitter(article_of_the_day)
    except Exception as err:
        error_message = {
            'text': '@edwin Something went wrong posting the Article of the Day to Twitter:\n%s'%err,
            'link_names': 1
        }
    if not twitter:
        error_message = {
            'text': '@edwin Unable to post the Article of the Day to Twitter:\n%s'%twitter,
            'link_names': 1
        }
    if error_message:
        try:
            res = post_to_slack(error_message)
        except:
            res = 'failed'
        sys.exit('Something went wrong posting the Article of the Day to Twitter. Post to Slack: %s' % res)
    # With a successful post we add this article to the library containing all the articles
    # that have been posted
    res = update_main_library(article_of_the_day['bibcode'])
        
