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

driver = webdriver.Chrome()

def main(url, output, depth, pages):
    g = networkx.Graph()
    for from_pub, to_pub in get_citations(url, depth=depth, pages=pages):
        g.add_node(from_pub['id'], label=from_pub['title'], **remove_nones(from_pub))
        g.add_node(to_pub['id'], label=to_pub['title'], **remove_nones(to_pub))
        g.add_edge(from_pub['id'], to_pub['id'])
        print('%s -> %s' % (from_pub['title'], to_pub['title']))
    networkx.write_gexf(g, '%s.gexf' % output) 
    write_html(g, '%s.html' % output)
    driver.close()

def get_citations(url, depth=1, pages=1):
    """
    Given a page of citations it will return bibliographic information
    for the source, target of a citation.
    """
    html = get_html(url)

    # get the publication that these are a citation for
    a = html.find('#gs_rt_hdr a', first=True)
    if a:
        to_pub = {
            'id': parse_qs(urlparse(a.attrs['href']).query)['cluster'][0],
            'title': a.text,
        }
    else: 
        to_pub = None

    # now find all the citations
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

        for a in e.find('.gs_fl a'):
            if 'Cited by' in a.text:
                cited_by = a.search('Cited by {:d}')[0]
                cited_by_url = 'https://scholar.google.com' + a.attrs['href']
                article_id = parse_qs(urlparse(cited_by_url).query)['cites'][0]
                break

        from_pub = {
            'id': article_id,
            'url': url,
            'title': title,
            'authors': authors,
            'year': year,
            'cited_by': cited_by,
            'cited_by_url': cited_by_url
        }

        yield from_pub, to_pub

        if depth > 0:
            yield from get_citations(
                from_pub['cited_by_url'],
                depth=depth-1,
                pages=pages
            )

    if pages > 1:
        for link in html.find('#gs_n a'):
            if link.text == 'Next':
                yield from get_citations(
                    'https://scholar.google.com' + link.attrs['href'],
                    depth=depth,
                    pages=pages-1
                )


def get_html(url):
    """
    get_html uses selenium to drive a browser to fetch a URL, and return a
    requests_html.HTML object for it.
    
    If there is a captcha challenge it will alert the user and wait until 
    it has been completed.
    """
    print(url)
    time.sleep(random.randint(1,5))
    driver.get(url)
    while True:
        try:
            recap = driver.find_element_by_css_selector('#gs_captcha_ccl,#recaptcha')
        except NoSuchElementException:


            html = driver.find_element_by_css_selector('#gs_top').get_attribute('innerHTML')
            return requests_html.HTML(html=html)
        print("... it's captcha time!\a ...")
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
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--depth', type=int, default=1)
    parser.add_argument('--pages', type=int, default=1)
    parser.add_argument('--output', type=str, default='output')
    args = parser.parse_args()
    main(args.url, output=args.output, depth=args.depth, pages=args.pages)
