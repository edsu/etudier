#!/usr/bin/env python

import re
import sys
import math
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
group = []
min_cited_by = 9999999
max_size = 0

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

    # add size and score to nodes
    update_nodes(g)

    # write the output files
    networkx.write_gexf(g, '%s.gexf' % args.output)
    write_html(g, args.depth+1, '%s.html' % args.output)

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

def update_nodes(g):
    """
    Add attributes of size, score (fractional from of group number) to
    nodes.
    """
    global group
    global min_cited_by
    global max_size

    try:
        for key in g.nodes.keys():
            if 'cited_by' in g.nodes[key]:
                g.nodes[key]['size'] = int(math.sqrt(
                    g.nodes[key]['cited_by']/min_cited_by))
            else:
                g.nodes[key]['size'] = 1
            if g.nodes[key]['size'] > max_size:
                max_size = g.nodes[key]['size']

            if 'group' in g.nodes[key]:
                g.nodes[key]['score'] = float(
                    g.nodes[key]['group'])/len(group)
            else:
                g.nodes[key]['score'] = 0
    except Exception as msg:
        breakpoint()
        exit(msg)

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
    a = html.find('#gs_res_ccl_top a', first=True)
    if a:
        to_pub = {
            'id': get_cluster_id(url),
            'title': a.text,
        }
    else:
        to_pub = None

    for e in html.find('#gs_res_ccl_mid .gs_r'):

        from_pub = get_metadata(e, to_pub['id'])
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

def get_metadata(e, parent_id):
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

    global min_cited_by
    cited_by = cited_by_url = None
    for a in e.find('.gs_fl a'):
        if 'Cited by' in a.text:
            cited_by = a.search('Cited by {:d}')[0]
            if cited_by < min_cited_by:
                min_cited_by = cited_by
            cited_by_url = 'https://scholar.google.com' + a.attrs['href']

    global group

    if parent_id not in group:
        group.append(parent_id)

    group_num = group.index(parent_id) + 1

    return {
        'id': article_id,
        'parent_id': parent_id,
        'group': group_num,
        'url': url,
        'title': title,
        'authors': authors,
        'year': year,
        'cited_by': cited_by,
        'cited_by_url': cited_by_url,
        'type': 'circle',
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
            recap = driver.find_element_by_css_selector(
                '#gs_captcha_ccl,#recaptcha')
        except NoSuchElementException:

            try:
                html = driver.find_element_by_css_selector('#gs_top').\
                        get_attribute('innerHTML')
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

def write_html(g, depth, output):
    graph_data = json.dumps(to_json(g), indent=2)
    html = """<!DOCTYPE html>
<meta charset="utf-8">
<style>
body {
  overflow:hidden;
   margin:0;
}

text {
  font-family: sans-serif;
  pointer-events: none;
}

</style>
<body>
<script src="https://d3js.org/d3.v3.min.js"></script>
<script>
var w = window.innerWidth;
var h = window.innerHeight;

var keyc = true, keys = true, keyt = true, keyr = true, keyx = true, keyd = true, keyl = true, keym = true, keyh = true, key1 = true, key2 = true, key3 = true, key0 = true

var focus_node = null, highlight_node = null;

var text_center = false;
var outline = false;

var min_score = 0;
var max_score = 1;

var color = d3.scale.linear()
  .domain([min_score, (min_score+max_score)/4, (min_score+max_score)/2,
      (min_score+max_score)*3/4, max_score])
  .range(["lime", "yellow", "red", "deepskyblue"]);

var highlight_color = "blue";
var highlight_trans = 0.1;

var size = d3.scale.pow().exponent(1)
  .domain([1,%d])
  .range([8,24]);

var force = d3.layout.force()
  .linkDistance((4*h)/5/2/%d)
  .charge(-300)
  .size([w,h]);

var default_node_color = "#ccc";
//var default_node_color = "rgb(3,190,100)";
var default_link_color = "#888";
var nominal_base_node_size = 8;
var nominal_text_size = 10;
var max_text_size = 24;
var nominal_stroke = 1.5;
var max_stroke = 4.5;
var max_base_node_size = 36;
var min_zoom = 0.1;
var max_zoom = 7;
var svg = d3.select("body").append("svg");
var zoom = d3.behavior.zoom().scaleExtent([min_zoom,max_zoom])
var g = svg.append("g");
svg.style("cursor","move");

var graph = %s;

var linkedByIndex = {};
    graph.links.forEach(function(d) {
    linkedByIndex[d.source + "," + d.target] = true;
    });

function isConnected(a, b) {
    return linkedByIndex[a.index + "," + b.index] || linkedByIndex[b.index + "," + a.index] || a.index == b.index;
}

function hasConnections(a) {
    for (var property in linkedByIndex) {
            s = property.split(",");
            if ((s[0] == a.index || s[1] == a.index) && linkedByIndex[property])                    return true;
    }
return false;
}

force.size([2*w/3, h])

force
  .nodes(graph.nodes)
  .links(graph.links)
  .start();

var link = g.selectAll(".link")
  .data(graph.links)
  .enter().append("line")
  .attr("class", "link")
  .style("stroke-width",nominal_stroke)
  .style("stroke", function(d) {
  if (isNumber(d.score) && d.score>=0) return color(d.score);
  else return default_link_color; })


var node = g.selectAll(".node")
  .data(graph.nodes)
  .enter().append("g")
  .attr("class", "node")
  .call(force.drag)

var timeout = null;

node.on("click", function(d) {
    clearTimeout(timeout);

    timeout = setTimeout(function() {
      window.open(d.url, '_blank');
      d3.event.stopPropagation();
    }, 300)
});

node.on("dblclick.zoom", function(d) {
    clearTimeout(timeout);

    d3.event.stopPropagation();
    var dcx = (window.innerWidth/2-d.x*zoom.scale());
    var dcy = (window.innerHeight/2-d.y*zoom.scale());
    zoom.translate([dcx,dcy]);
    g.attr("transform", "translate("+ dcx + "," + dcy  + ")scale(" + zoom.scale() + ")");
});

var tocolor = "fill";
var towhite = "stroke";
if (outline) {
    tocolor = "stroke"
    towhite = "fill"
}

var circle = node.append("path")
    .attr("d", d3.svg.symbol()
    .size(function(d) { return Math.PI*Math.pow(size(d.size)||nominal_base_node_size,2); })
    .type(function(d) { return d.type; }))
    .style(tocolor, function(d) {
        if (isNumber(d.score) && d.score>=0) return color(d.score);
        else return default_node_color; })
    //.attr("r", function(d) { return size(d.size)||nominal_base_node_size; })
    .style("stroke-width", nominal_stroke)
    .style(towhite, "white");

var text = g.selectAll(".text")
  .data(graph.nodes)
  .enter().append("text")
  .attr("dy", ".35em")
  .style("font-size", nominal_text_size + "px")

  if (text_center)
   text.text(function(d) { return (d.authors ? d.title+' - '+d.authors :
       d.title); })
  .style("text-anchor", "middle");
  else 
  text.attr("dx", function(d) {return (size(d.size)||nominal_base_node_size);})
  .text(function(d) { return ' '+(d.authors ? d.title+' - '+d.authors :
       d.title); });

  node.on("mouseover", function(d) {
  set_highlight(d);
  })
  .on("mousedown", function(d) { d3.event.stopPropagation();
    focus_node = d;
    set_focus(d)
    if (highlight_node === null) set_highlight(d)

}   ).on("mouseout", function(d) {
        exit_highlight();

}   );

        d3.select(window).on("mouseup",
        function() {
        if (focus_node!==null)
        {
            focus_node = null;
            if (highlight_trans<1)
            {

        circle.style("opacity", 1);
      text.style("opacity", 1);
      link.style("opacity", 1);
    }
        }

    if (highlight_node === null) exit_highlight();
        });

function exit_highlight()
{
        highlight_node = null;
    if (focus_node===null)
    {
        svg.style("cursor","move");
        if (highlight_color!="white")
    {
      circle.style(towhite, "white");
      text.style("font-weight", "normal");
      link.style("stroke", function(o) {return (isNumber(o.score) && o.score>=0)?color(o.score):default_link_color});
 }
            
    }
}

function set_focus(d)
{   
if (highlight_trans<1)  {
    circle.style("opacity", function(o) {
                return isConnected(d, o) ? 1 : highlight_trans;
            });

            text.style("opacity", function(o) {
                return isConnected(d, o) ? 1 : highlight_trans;
            });

            link.style("opacity", function(o) {
                return o.source.index == d.index || o.target.index == d.index ? 1 : highlight_trans;
            });     
    }
}


function set_highlight(d)
{
    svg.style("cursor","pointer");
    if (focus_node!==null) d = focus_node;
    highlight_node = d;

    if (highlight_color!="white")
    {
          circle.style(towhite, function(o) {
                return isConnected(d, o) ? highlight_color : "white";});
            text.style("font-weight", function(o) {
                return isConnected(d, o) ? "bold" : "normal";});
            link.style("stroke", function(o) {
              return o.source.index == d.index || o.target.index == d.index ? highlight_color : ((isNumber(o.score) && o.score>=0)?color(o.score):default_link_color);

            });
    }
}

  zoom.on("zoom", function() {

    var stroke = nominal_stroke;
    if (nominal_stroke*zoom.scale()>max_stroke) stroke = max_stroke/zoom.scale();
    link.style("stroke-width",stroke);
    circle.style("stroke-width",stroke);

    var base_radius = nominal_base_node_size;
    if (nominal_base_node_size*zoom.scale()>max_base_node_size) base_radius = max_base_node_size/zoom.scale();
        circle.attr("d", d3.svg.symbol()
        .size(function(d) { return Math.PI*Math.pow(size(d.size)*base_radius/nominal_base_node_size||base_radius,2); })
        .type(function(d) { return d.type; }))

    //circle.attr("r", function(d) { return (size(d.size)*base_radius/nominal_base_node_size||base_radius); })
    if (!text_center) text.attr("dx", function(d) { return (size(d.size)*base_radius/nominal_base_node_size||base_radius); });

    var text_size = nominal_text_size;
    if (nominal_text_size*zoom.scale()>max_text_size) text_size = max_text_size/zoom.scale();
    text.style("font-size",text_size + "px");

    g.attr("transform", "translate(" + d3.event.translate + ")scale(" + d3.event.scale + ")");
    });

  svg.call(zoom);

  resize();
  //window.focus();
  d3.select(window).on("resize", resize).on("keydown", keydown);

  force.on("tick", function() {

    node.attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });
    text.attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });

    link.attr("x1", function(d) { return d.source.x; })
      .attr("y1", function(d) { return d.source.y; })
      .attr("x2", function(d) { return d.target.x; })
      .attr("y2", function(d) { return d.target.y; });
      node.attr("cx", function(d) { return d.x; })
      .attr("cy", function(d) { return d.y; });
    });

  function resize() {
    var width = window.innerWidth, height = window.innerHeight;
    svg.attr("width", width).attr("height", height);

    force.size([force.size()[0]+(width-w)/zoom.scale(),force.size()[1]+(height-h)/zoom.scale()]).resume();
    w = width;
    h = height;
    }

    function keydown() {
    if (d3.event.keyCode==32) {  force.stop();}
    else if (d3.event.keyCode>=48 && d3.event.keyCode<=90 && !d3.event.ctrlKey && !d3.event.altKey && !d3.event.metaKey)
    {
  switch (String.fromCharCode(d3.event.keyCode)) {
    case "C": keyc = !keyc; break;
    case "S": keys = !keys; break;
    case "T": keyt = !keyt; break;
    case "R": keyr = !keyr; break;
    case "X": keyx = !keyx; break;
    case "D": keyd = !keyd; break;
    case "L": keyl = !keyl; break;
    case "M": keym = !keym; break;
    case "H": keyh = !keyh; break;
    case "1": key1 = !key1; break;
    case "2": key2 = !key2; break;
    case "3": key3 = !key3; break;
    case "0": key0 = !key0; break;
  }

  link.style("display", function(d) {
                var flag  = vis_by_type(d.source.type)&&vis_by_type(d.target.type)&&vis_by_node_score(d.source.score)&&vis_by_node_score(d.target.score)&&vis_by_link_score(d.score);
                linkedByIndex[d.source.index + "," + d.target.index] = flag;
              return flag?"inline":"none";});
  node.style("display", function(d) {
                return (key0||hasConnections(d))&&vis_by_type(d.type)&&vis_by_node_score(d.score)?"inline":"none";});
  text.style("display", function(d) {
                return (key0||hasConnections(d))&&vis_by_type(d.type)&&vis_by_node_score(d.score)?"inline":"none";});
                if (highlight_node !== null)
                {
                    if ((key0||hasConnections(highlight_node))&&vis_by_type(highlight_node.type)&&vis_by_node_score(highlight_node.score)) { 
                    if (focus_node!==null) set_focus(focus_node);
                    set_highlight(highlight_node);
                    }
                    else {exit_highlight();}
                }

}
}

function vis_by_type(type)
{
    switch (type) {
      case "circle": return keyc;
      case "square": return keys;
      case "triangle-up": return keyt;
      case "diamond": return keyr;
      case "cross": return keyx;
      case "triangle-down": return keyd;
      default: return true;
}
}
function vis_by_node_score(score)
{
    if (isNumber(score))
    {
    if (score>=0.666) return keyh;
    else if (score>=0.333) return keym;
    else if (score>=0) return keyl;
    }
    return true;
}

function vis_by_link_score(score)
{
    if (isNumber(score))
    {
    if (score>=0.666) return key3;
    else if (score>=0.333) return key2;
    else if (score>=0) return key1;
}
    return true;
}

function isNumber(n) {
  return !isNaN(parseFloat(n)) && isFinite(n);
}


</script>
""" % (max_size, depth, graph_data)
    open(output, 'w').write(html)

if __name__ == "__main__":
    main()
