#!/usr/bin/env python

import re
import sys
import json
import time
import random
import argparse
import networkx
import requests_html

from pathlib import Path
from string import Template
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from urllib.parse import urlparse, parse_qs
from networkx.algorithms.community.modularity_max import greedy_modularity_communities


seen = set()
driver = None

def main():
    global driver

    parser = argparse.ArgumentParser()
    parser.add_argument('url', help="URL for a Google Scholar search to start collecting from")
    parser.add_argument('--depth', type=int, default=1, help="depth of the crawl in terms of levels of citation (defaults to 1)")
    parser.add_argument('--pages', type=int, default=1, help="breadth of the crawl in terms of number of pages of results (defaults to 1)")
    parser.add_argument('--output', type=str, default='output', help="file prefix to use for the output files (defaults to 'output')")
    parser.add_argument('--debug', action="store_true", default=False, help="display diagnostics during the crawl")
    args = parser.parse_args()

    # ready to start up headless browser
    driver = webdriver.Chrome()

    # create our graph that will get populated
    g = networkx.DiGraph()

    # iterate through all the citation links
    for from_pub, to_pub in get_citations(args.url, depth=args.depth, pages=args.pages):
        if args.debug:
            print('from: %s' % json.dumps(from_pub))
        g.add_node(from_pub['id'], label=from_pub['title'], **remove_nones(from_pub))
        if to_pub:
            if args.debug:
                print('to: %s' % json.dumps(to_pub))
            print('%s -> %s' % (from_pub['id'], to_pub['id']))
            g.add_node(to_pub['id'], label=to_pub['title'], **remove_nones(to_pub))
            g.add_edge(from_pub['id'], to_pub['id'])

        # generate output as we go in the case of sisyphean google captcha 
        write_output(g, args)

    # cluster the nodes using neighborhood detection
    #write_output(g, args)

    # close the browser
    driver.close()

def to_json(g):
    """
    Source and target of links are index of corresponding nodes.
    """
    j = {"nodes": [], "links": []}
    for node_id, node_attrs in g.nodes(True):
        node_attrs['id'] = node_id
        j["nodes"].append(node_attrs)
    for source, target, attrs in g.edges(data=True):
        index = 0
        for node_id, node_attrs in g.nodes(True):
            if source == node_id:
                source = index
            if target == node_id:
                target = index
            index += 1
        j["links"].append({
            "source": source,
            "target": target
        })

    return j

def cluster_nodes(g):
    """
    Use Clauset-Newman-Moore greedy modularity maximization to cluster nodes.
    """
    undirected_g = networkx.Graph(g)
    for i, comm in enumerate(greedy_modularity_communities(undirected_g)):
        for node in comm:
            g.nodes[node]['modularity'] = i
    return g

def get_cluster_id(url):
    """
    Google assign a cluster identifier to a group of web documents
    that appear to be the same publication in different places on the web.
    How they do this is a bit of a mystery, but this identifier is
    important since it uniquely identifies the publication.
    """
    vals = parse_qs(urlparse(url).query).get('cluster', [])
    if len(vals) == 1:
        return vals[0]
    else:
        vals = parse_qs(urlparse(url).query).get('cites', [])
        if len(vals) == 1:
            return vals[0]
    return None

def get_id(e):
    """
    Determining the publication id is tricky since it involves looking
    in the element for the various places a cluster id can show up.
    If it can't find one it will use the data-cid which should be
    usable since it will be a dead end anyway: Scholar doesn't know of
    anything that cites it.
    """
    for a in e.find('.gs_fl a'):
        if 'Cited by' in a.text:
            return get_cluster_id(a.attrs['href'])
        elif 'versions' in a.text:
            return get_cluster_id(a.attrs['href'])
    return e.attrs.get('data-cid')

def get_citations(url, depth=1, pages=1):
    """
    Given a page of citations it will return bibliographic information
    for the source, target of a citation.
    """
    if url in seen:
        return

    html = get_html(url)
    seen.add(url)

    # get the publication that these citations reference.
    # Note: this can be None when starting with generic search results
    a = html.find('#gs_res_ccl_top a', first=True)
    if a:
        to_pub = {
            'id': get_cluster_id(url),
            'title': a.text,
        }
        # try to get the total results for the item we are searching within
        results = html.find('#gs_ab_md .gs_ab_mdw', first=True)
        if results:
            m = re.search('([0-9,]+) results', results.text)
            if m:
                to_pub['cited_by'] = int(m.group(1).replace(',', ''))
    else:
        to_pub = None

    for e in html.find('#gs_res_ccl_mid .gs_r'):
        from_pub = get_metadata(e, to_pub)
        if from_pub:
            yield from_pub, to_pub
        else:
            continue

        # depth first search if we need to go deeper
        if depth > 0 and from_pub['cited_by_url']:
            yield from get_citations(
                from_pub['cited_by_url'],
                depth=depth-1,
                pages=pages
            )

    # get the next page if that's what they wanted
    if pages > 1:
        for link in html.find('#gs_n a'):
            if link.text == 'Next':
                yield from get_citations(
                    'https://scholar.google.com' + link.attrs['href'],
                    depth=depth,
                    pages=pages-1
                )

def get_metadata(e, to_pub):
    """
    Fetch the citation metadata from a citation element on the page.
    """
    article_id = get_id(e)
    if not article_id:
        return None

    a = e.find('.gs_rt a', first=True)
    if a:
        url = a.attrs['href']
        title = a.text
    else:
        url = None
        title = e.find('.gs_rt .gs_ctu', first=True).text

    authors = source = website = None
    meta = e.find('.gs_a', first=True).text
    meta_parts = [m.strip() for m in re.split(r'\W-\W', meta)]
    if len(meta_parts) == 3:
        authors, source, website = meta_parts
    elif len(meta_parts) == 2:
        authors, source = meta_parts

    if source and ',' in source:
        year = source.split(',')[-1].strip()
    else:
        year = source

    cited_by = cited_by_url = None
    for a in e.find('.gs_fl a'):
        if 'Cited by' in a.text:
            cited_by = a.search('Cited by {:d}')[0]
            cited_by_url = 'https://scholar.google.com' + a.attrs['href']

    return {
        'id': article_id,
        'url': url,
        'title': title,
        'authors': authors,
        'year': year,
        'cited_by': cited_by,
        'cited_by_url': cited_by_url,
    }

def get_html(url):
    """
    get_html uses selenium to drive a browser to fetch a URL, and return a
    requests_html.HTML object for it.
    
    If there is a captcha challenge it will alert the user and wait until 
    it has been completed.
    """
    global driver

    if driver is None:
        raise Exception("driver is not configured!")

    time.sleep(random.randint(1,5))
    driver.get(url)
    while True:
        try:
            driver.find_element(By.CSS_SELECTOR, '#gs_captcha_ccl,#recaptcha')
        except NoSuchElementException:

            try:
                html = driver.find_element(By.CSS_SELECTOR,'#gs_top').get_attribute('innerHTML')
                return requests_html.HTML(html=html)
            except NoSuchElementException:
                print("google has blocked this browser, reopening")
                driver.close()
                driver = webdriver.Chrome()
                return get_html(url)

        print("... it's CAPTCHA time!\a ...")
        time.sleep(5)

def remove_nones(d):
    new_d = {}
    for k, v in d.items():
        if v is not None:
            new_d[k] = v
    return new_d

def write_output(g, args):
    cluster_nodes(g)
    networkx.write_gexf(g, '%s.gexf' % args.output)
    networkx.write_graphml(g, '%s.graphml' % args.output)
    write_html(g, '%s.html' % args.output)

def write_html(g, output):
    graph_json = json.dumps(to_json(g), indent=2)
    html_file = Path(__file__).parent / "network.html"
    opts = ' '.join(sys.argv[1:])
    tmpl = Template(html_file.open().read())
    html = tmpl.substitute({
        "__OPTIONS__": opts,
        "__GRAPH_JSON__": graph_json
    })
    Path(output).open('w').write(html)

if __name__ == "__main__":
    main()
