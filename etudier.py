#!/usr/bin/env python

import re
import sys
import json
import time
import random
import argparse
import networkx
import requests_html

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import urlparse, parse_qs

seen = set()
driver = None

def main():
    global driver

    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--depth', type=int, default=1)
    parser.add_argument('--pages', type=int, default=1)
    parser.add_argument('--output', type=str, default='output')
    parser.add_argument('--debug', action="store_true", default=False)
    args = parser.parse_args()

    # ready to start up headless browser
    driver = webdriver.Chrome()

    # create our graph that will get populated
    g = networkx.Graph()

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

    # write the output files
    networkx.write_gexf(g, '%s.gexf' % args.output) 
    write_html(g, '%s.html' % args.output)

    # close the browser
    driver.close()

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
    return e.attrs['data-cid']

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
    a = html.find('#gs_rt_hdr a', first=True)
    if a:
        to_pub = {
            'id': get_cluster_id(url),
            'title': a.text,
        }
    else: 
        to_pub = None

    for e in html.find('.gs_r'):

        from_pub = get_metadata(e)
        yield from_pub, to_pub

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

def get_metadata(e):
    """
    Fetch the citation metadata from a citation element on the page.
    """
    article_id = get_id(e)

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
        'cited_by_url': cited_by_url
    }

def get_html(url):
    """
    get_html uses selenium to drive a browser to fetch a URL, and return a
    requests_html.HTML object for it.
    
    If there is a captcha challenge it will alert the user and wait until 
    it has been completed.
    """
    global driver

    time.sleep(random.randint(1,5))
    driver.get(url)
    while True:
        try:
            recap = driver.find_element_by_css_selector('#gs_captcha_ccl,#recaptcha')
        except NoSuchElementException:

            try:
                html = driver.find_element_by_css_selector('#gs_top').get_attribute('innerHTML')
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

def write_html(g, output):
    graph_data = json.dumps(to_json(g), indent=2)
    html = """<!DOCTYPE html>
<meta charset="utf-8">
<script src="https://platform.twitter.com/widgets.js"></script>
<script src="https://d3js.org/d3.v4.min.js"></script>
<script src="https://code.jquery.com/jquery-3.1.1.min.js"></script>
<style>

.links line {
  stroke: #999;
  stroke-opacity: 0.8;
  stroke-width: 2px;
}

.nodes circle {
  stroke: black;
  fill: white;
  stroke-width: 1.5px;
}

#graph {
  width: 99vw;
  height: 99vh;
}

</style>
<svg id="graph"></svg>
<script>

var width = $(window).width();
var height = $(window).height();

var svg = d3.select("svg")
    .attr("height", height)
    .attr("width", width);

var color = d3.scaleOrdinal(d3.schemeCategory20c);

var simulation = d3.forceSimulation()
    .velocityDecay(0.6)
    .force("link", d3.forceLink().id(function(d) { return d.id; }))
    .force("charge", d3.forceManyBody())
    .force("center", d3.forceCenter(width / 2, height / 2));

var graph = %s;

var link = svg.append("g")
    .attr("class", "links")
  .selectAll("line")
  .data(graph.links)
  .enter().append("line");

var node = svg.append("g")
    .attr("class", "nodes")
  .selectAll("circle")
  .data(graph.nodes)
  .enter().append("circle")
    .attr("r", 5)
    .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

node.append("title")
    .text(function(d) {
        return d.authors ? d.title + ' - ' + d.authors : d.title
    });

node.on("click", function(d) {
  window.open(d.url, '_blank');
  d3.event.stopPropagation();
});

simulation
    .nodes(graph.nodes)
    .on("tick", ticked);

simulation.force("link")
    .links(graph.links);

function ticked() {
  link
      .attr("x1", function(d) { return d.source.x; })
      .attr("y1", function(d) { return d.source.y; })
      .attr("x2", function(d) { return d.target.x; })
      .attr("y2", function(d) { return d.target.y; });

  node
      .attr("cx", function(d) { return d.x; })
      .attr("cy", function(d) { return d.y; });
}

function dragstarted(d) {
  if (!d3.event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x;
  d.fy = d.y;
}

function dragged(d) {
  d.fx = d3.event.x;
  d.fy = d3.event.y;
}

function dragended(d) {
  if (!d3.event.active) simulation.alphaTarget(0);
  d.fx = null;
  d.fy = null;
}

</script>
""" % graph_data
    open(output, 'w').write(html)

def to_json(g):
    j = {"nodes": [], "links": []}
    for node_id, node_attrs in g.nodes(True):
        node_attrs['id'] = node_id
        j["nodes"].append(node_attrs)
    for source, target, attrs in g.edges(data=True):
        j["links"].append({
            "source": source,
            "target": target
        })
    return j

if __name__ == "__main__":
    main()

