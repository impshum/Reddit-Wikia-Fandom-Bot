import praw
import configparser
import re
from bs4 import BeautifulSoup
import requests
import wikia
import urllib.parse
import time


def lovely_soup(url):
    r = requests.get(url, headers={
                     'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1'})
    return BeautifulSoup(r.text, 'lxml')


def did_you_mean(url):
    soup = lovely_soup(url)
    alternative = soup.find('span', {'class': 'alternative-suggestion'})
    if alternative:
        return alternative.find('a')['href']


def get_wikia(wikia_title, query):
    try:
        response = wikia.summary(wikia_title, query)
        if response.startswith('REDIRECT '):
            query = response.replace('REDIRECT ', '')
        return wikia.summary(wikia_title, query)
    except wikia.WikiaError as e:
        print(e)


def get_wikia_url(wikia_title, query):
    try:
        wurl = wikia.page(wikia_title, query)
        return wurl.url.replace(' ', '_')
    except wikia.WikiaError as e:
        print(e)


def find_urls(s):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex, s)
    return [x[0] for x in url]


def get_query(wikia_title, url):
    query = urllib.parse.unquote(url.split('wiki/')[1])
    snippet = get_wikia(wikia_title, query)

    if not snippet:
        url = did_you_mean(url)
        if url:
            query = urllib.parse.unquote(url.split('wiki/')[1])
            snippet = get_wikia(wikia_title, query)

    if snippet:
        return {'query': query, 'snippet': snippet, 'url': url}


def process(object, type, text, wiki_urls, bot_footer, wikia_title, test_mode):
    the_reply = ''
    sources = []
    queries = []
    urls = []

    for url in find_urls(text):
        if url not in urls:
            urls.append(url)
            for wiki in wiki_urls:
                if wiki in url:
                    response = get_query(wikia_title, url)
                    if response:
                        source = response['url']
                        if source not in sources:
                            sources.append(source)
                            snippet = response['snippet']
                            query = response['query'].replace('_', ' ')
                            queries.append(query)
                            reply_text = f'### {query} | {source}  \n{snippet}\n\n---\n\n'
                            the_reply += reply_text

    if len(the_reply):
        if not test_mode:
            try:
                object.reply(f"{the_reply}{bot_footer}".strip())
            except Exception as e:
                print(e)
        now = time.ctime(object.created_utc)
        print(f'{now} | {type} - https://reddit.com{object.permalink}')


def linkify(object, type, keyword, text, bot_footer, wikia_title, test_mode):
    text = text.replace(f'{keyword} ', '')
    source = get_wikia_url(wikia_title, text)
    snippet = get_wikia(wikia_title, text)
    the_reply = f'### {text} | {source}  \n{snippet}\n\n---\n\n'

    if not test_mode:
        try:
            object.reply(f"{the_reply}{bot_footer}".strip())
        except Exception as e:
            print(e)
    now = time.ctime(object.created_utc)
    print(f'{now} | {type} - https://reddit.com{object.permalink}')


def streamer(subreddit, **kwargs):
    results = []
    results.extend(subreddit.new(**kwargs))
    results.extend(subreddit.comments(**kwargs))
    results.sort(key=lambda post: post.created_utc, reverse=True)
    return results


def main():
    config = configparser.ConfigParser()
    config.read('conf.ini')
    reddit_user = config['REDDIT']['reddit_user']
    reddit_pass = config['REDDIT']['reddit_pass']
    reddit_client_id = config['REDDIT']['reddit_client_id']
    reddit_client_secret = config['REDDIT']['reddit_client_secret']
    target_subreddit = config['SETTINGS']['target_subreddit']
    bot_footer = config['SETTINGS']['bot_footer']
    wikia_title = config['SETTINGS']['wikia_title']
    keyword = config['SETTINGS']['keyword']
    test_mode = config['SETTINGS'].getboolean('test_mode')

    if test_mode:
        print('\nTEST MODE\n')

    reddit = praw.Reddit(
        username=reddit_user,
        password=reddit_pass,
        client_id=reddit_client_id,
        client_secret=reddit_client_secret,
        user_agent='Fandom/Wikia Bot (by u/impshum)'
    )

    subreddit = reddit.subreddit(target_subreddit)

    stream = praw.models.util.stream_generator(
        lambda **kwargs: streamer(subreddit, **kwargs))

    wiki_urls = [f'{wikia_title}.fandom.com/wiki/',
                 f'{wikia_title}.wikia.com/wiki/']

    for post in stream:
        if post.created_utc != time.time():
            if post.author.name != reddit_user:
                try:
                    body = post.selftext
                    type = 'submission'
                except AttributeError:
                    body = post.body
                    type = 'comment'

                if type == 'comment' and body.startswith(f'{keyword} '):
                    linkify(post, type, keyword, body, bot_footer,
                            wikia_title, test_mode)
                else:
                    process(post, type, body, wiki_urls,
                            bot_footer, wikia_title, test_mode)


if __name__ == '__main__':
    main()
