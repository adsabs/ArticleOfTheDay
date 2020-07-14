# ADS Article of the Day
## Summary
Back in 2012 the ADS Article of the Day was introduced. Every work day an "ADS Article Day" has been posted on social media with the hashtag #adsarticleoftheday (currently only on Twitter). This is envisioned to be a selection from recent, current additions to the ADS database that meets certain criteria. In practice this means

1. **Recent:** added to the ADS holdings within the previous 3 weeks
2. **Current:** published in the year at hand (or including the previous year in January)
3. **Meeting certain criteria:** this is the "secret sauce" that should take care of "relevance" and "diversity" in content. It does so using the following ingredients:

	* The resulting 5 articles should preferably be about different topics
	* The articles should preferably be from different journals
	* They must have a *doctype* of *article*
	* They must have been read and cited

## Implementation
Main design principles for redesigning the ADS Article of the Day service were the following

* Break all dependency on ADS Classic
* Make use of the ADS API for all data calls
* Make use of the ADS Libraries system to store data:
	* All articles posted so far
	* The current batch of Articles of the Day
* All functionality (generating batches and posting) must be part of one environment
* The code must be written in Python 3.8

The implementation in this repository uses *Flask-Script* to define a CLI used to **generate** a new batch and to **post** an article from the current batch.
### Selecting a new batch
The batch of 5 articles that will be posted each work day on social media (Twitter) starts off with generating a larger set of candidates. The larger set of candidates is retrieved through the API by sending the following query to Solr

> entry_date:["NOW-21DAYS" TO NOW] collection:astronomy doctype:article year:YYYY

Here, the publication year field is either the current year or the range spanning the current year and previous year (when the current month is January). From the resulting set of records, all records are removed that already appeared as Article of the Day.

This set of candidates is segmented into a set of clusters based on the citation network generated from this set. An article is selecting from each cluster and the final set of 5 *Articles of the Day* is a random selection from this set. The code has a Slack integration where this selection will be posted to the associated channel.

This set if stored in an ADS Library from which one is paicked each work day.
### Posting the Article of the Day
The Article of the Day is posted to Twitter using the Python module **tweepy**. In order to be able to post to Twitter an app was registered with the adsabs Twitter account. In this implementation the approach of OAuth 1a authentication was taken. Articles are posted with the hashtag *#adsarticleoftheday*.