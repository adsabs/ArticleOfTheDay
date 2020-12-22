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
    if current_date.month == 1:
        year_range = "%s-%s" % (current_date.year - 1, current_date.year)
    else:
        year_range = str(current_date.year)
    try:
        data = get_data(year_range)
    except:
        current_app.logger.exception("Failed to retrieve initial metadata from Solr")
        error = {
            'Error':'Failed to retrieve initial metadata from Solr',
            'Slack':'@edwin Failed to retrieve initial metadata from Solr for new Article of the Day batch. Please check logs.'
        }
        return error
    # From the initial dataset, get the actual candidates by
    # 1. removing all publications that we used previously
    try:
        clean_data = cleanup_data(data)
    except:
        current_app.logger.exception("Failed to clean up data (remove publications used previously)")
        error = {
            'Error':'Failed to clean up data (remove publications used previously)',
            'Slack':'@edwin Failed to clean up data for Article of the Day batch. Please check logs.'
        }
        return error
    # Create a paper network based on the candidates found
    # This network will be segmented into clusters. These clusters will be used to find candidates.
    try:
        visdata = paper_network.get_papernetwork(clean_data, current_app.config.get("MAX_GROUPS"))
    except:
        current_app.logger.exception("Failed to create a paper network based on the candidates found")
        error = {
            'Error':'Failed to create a paper network based on the candidates found',
            'Slack':'@edwin Failed to create a paper network for the Article of the Day batch. Please check logs.'
        }
        return error
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
            current_app.logger.exception("Failed to calculate weight for node {0}, switching to cite_read_boost".format(node['node_name']))
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
    try:
        new_batch = sample(candidates, 5)
    except:
        current_app.logger.exception('Failed to create new batch')
        error = {
            'Error':'Failed to create new batch',
            'Slack':'@edwin Failed to create new batch for the Article of the Day. Please check logs.'
        }
        return error
    # If the new batch has less than 5 articles, sound the alarm
    if len(new_batch) < 5:
        current_app.logger.error('AoD batch less then 5 records: {0}'.format(len(new_batch)))
        error = {
            'Error':'AoD batch is too small',
            'Slack': '@edwin Found only %s articles instead of 5! Check logs!' % len(new_batch)
        }
        return error
    # Store the new batch in the appropriate ADS Library
    try:
        saved_batch = save_new_batch(new_batch)
    except Exception as err:
        current_app.logger.error('Something went wrong saving the current AoD batch: {0}'.format(err))
        error = {
            'Error':'Something went wrong saving the current AoD batch: {0}'.format(err),
            'Slack': '@edwin Something went wrong saving the current AoD batch:\n{0}'.format(err)
        }
        return error
    # Check that 5 records were posted
    try:
        number_added = saved_batch['number_added']
    except:
        number_added = 0
    if number_added != 5:
        current_app.logger.error('Something went wrong saving the current AoD batch: less than 5 records added')
        error = {
            'Error':'Something went wrong saving the current AoD batch',
            'Slack': '@edwin Something went wrong saving the current AoD batch: less than 5 records added! Please check!'
        }
        return error
    # For each candidate, include the keywords of the cluster it came from
    subject = '<%s|Articles of the Day - batch %s/%s/%s>' % (saved_batch['library_url'], current_date.month, current_date.day,current_date.year)
    message = '```'
    for entry in new_batch:
        try:
            label = "; ".join([l.decode("utf-8") for l in cluster_labels[entry[0]]])
        except:
            current_app.logger.exception("Failed to create label for cluster")
            label = "NA"
        message += "%s\tlabel: %s\n"%(entry[1],label)
    message += '```'
    post_message = {
        'Slack': '@edwin %s\nEntries:\n%s' % (subject, message),
    }
    return post_message

def post_article():
    # Get one article from the current batch
    try:
        article_of_the_day = retrieve_article()
    except:
        current_app.logger.exception('Something went wrong retrieving the Article of the Day')
        error = {
            'Error':'Something went wrong retrieving the Article of the Day',
            'Slack':'@edwin Something went wrong retrieving the Article of the Day. Please check logs.'
        }
        return error
    # Now we can start posting the article
    # 1. post to Twitter
    try:
        twitter = post_to_twitter(article_of_the_day)
    except:
        current_app.logger.exception('Something went wrong posting the Article of the Day to Twitter')
        error = {
            'Error':'Something went wrong posting the Article of the Day to Twitter',
            'Slack':'@edwin Something went wrong posting the Article of the Day to Twitter. Please check logs.'
        }
        return error
    if not twitter:
        error = {
            'Error':'Unable to post the Article of the Day to Twitter',
            'Slack': '@edwin Unable to post the Article of the Day to Twitter:\n%s'%twitter
        }
        return error
    # With a successful post we add this article to the library containing all the articles
    # that have been posted
    try:
        res = update_main_library(article_of_the_day['bibcode'])
    except:
        current_app.logger.exception('Failed to update the Article of the Day main library')
        error = {
            'Error':'Failed to update the Article of the Day main library',
            'Slack':'@edwin Failed to update the Article of the Day main library. Please check logs.'
        }
        return error
    current_app.logger.info('Successfully posted Article of the Day {0} to Twitter'.format(article_of_the_day))
    post_message = {
        'Slack':'Successfully posted Article of the Day {0} to Twitter'.format(article_of_the_day['bibcode'])
    }
    return post_message
        
        
