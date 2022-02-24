API_TOKEN = "your token"
SLACK_END_POINT = 'https://hooks.slack.com/services/TOKEN/TOKEN'
SOLR_PATH = 'https://api.adsabs.harvard.edu/v1/search/query'
LIBRARY_PATH = 'https://api.adsabs.harvard.edu/v1/biblib'
ADS_LIBRARY_PATH = 'https://ui.adsabs.harvard.edu/public-libraries'
ABSTRACT_PATH = 'https://ui.adsabs.harvard.edu/#abs'
QUERY = 'entry_date:["NOW-21DAYS" TO NOW] collection:astronomy doctype:article'
FIELDS = 'bibcode,year,citation_count,read_count,author_count,cite_read_boost,keywords,title,abstract,authors_norm,first_author,reference'
MAX_HITS = 1000
MAX_GROUPS = 10
AOD_LIBRARY_NAME = 'ADS Articles of the Day'
BATCH_LIBRARY_NAME = 'Current ADS Article of the Day batch'
AOD_UTM_TAGS = {
    'utm_source':'pyscript',
    'utm_medium':'tweet',
    'utm_campaign':'ADSaotd',
    'utm_content':'aotd'
}
TWITTER_TAG = '#ADSarticleOfTheDay'
TWITTER_CONSUMER_KEY = 'consumerkey'
TWITTER_CONSUMER_SECRET = 'consumersecret'
TWITTER_ACCESS_KEY = 'accesskey'
TWITTER_ACCESS_SECRET = 'accesssecret'
TWITTER_POST_LENGTH = 280
TWITTER_URL_LENGTH = 23
