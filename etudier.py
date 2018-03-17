#!/usr/bin/env python

import re
import csv
import sys
import json
import time
import random
import requests_html

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import urlparse, parse_qs

driver = webdriver.Chrome()

def get_citations(url):
    html = get_html(url)
    for e in html.find('.gs_r'):
        a = e.find('.gs_rt a', first=True)
        if a:
            url = a.attrs['href']
            title = a.text
        else:
            url = None
            title = e.find('.gs_rt .gs_ctu', first=True).text

        meta = e.find('.gs_a', first=True).text
        meta_parts = [m.strip() for m in re.split(r'\W-\W', meta)]
        if len(meta_parts) == 3:
            authors, source, website = meta_parts
        elif len(meta_parts) == 2:
            authors, source = meta_parts

        if ',' in source:
            year = source.split(',')[1].strip()
        else:
            year = source

        authors = [a.strip() for a in authors.split(',')]

        for a in e.find('.gs_fl a'):
            if 'Cited by' in a.text:
                cited_by = a.search('Cited by {:d}')[0]
                cited_by_url = 'https://scholar.google.com' + a.attrs['href']
                article_id = parse_qs(urlparse(cited_by_url).query)['cites'][0]
                break

        yield {
            'id': article_id,
            'url': url,
            'title': title,
            'authors': authors,
            'year': year,
            'cited_by': cited_by,
            'cited_by_url': cited_by_url
        }

def csvify(d):
    d['authors'] = ','.join(d['authors'])
    return d

def get_html(url):
    time.sleep(random.randint(1,5))
    driver.get(url)
    while True:
        try:
            recap = driver.find_element_by_css_selector('#gs_captcha_ccl')
        except NoSuchElementException:

            html = driver.find_element_by_css_selector('#gs_top').get_attribute('innerHTML')
            return requests_html.HTML(html=html)
        print('captcha time!')
        time.sleep(5)

edges = csv.DictWriter(open('edges.csv', 'w'), fieldnames=[
    'source',
    'target'
])
edges.writeheader()

nodes = csv.DictWriter(open('nodes.csv', 'w'), fieldnames=[
    'id',
    'url',
    'title',
    'authors',
    'year',
    'cited_by',
    'cited_by_url'
])
nodes.writeheader()

url = sys.argv[1]
seen = set()
for c1 in get_citations(url):
    if c1['id'] not in seen:
        nodes.writerow(csvify(c1))
        seen.add(c1['id'])
    for c2 in get_citations(c1['cited_by_url']):
        edges.writerow({
            'source': c2['id'],
            'target': c1['id']
        })
        if c2['id'] not in seen:
            nodes.writerow(csvify(c2))
            seen.add(c2['id'])


