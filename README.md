![Étudier in Action](figure.gif)

*étudier* is a small Python program that uses [Selenium], [requests-html] and
[networkx] to drive a *non-headless* browser to collect a citation graph around
a particular [Google Scholar] citation or set of search results. The resulting
network is written out as [GEXF] and [GraphML] files as well as an HTML file
that includes a [D3] network visualization (pictured above).

If you are wondering why it uses a non-headless browser it's because Google is
[quite protective] of this data and will routinely ask you to solve a captcha
(identifying street signs, cars, etc in photos) to prove you are not a bot.
*étudier* allows you to complete these captcha tasks when they occur and then it
continues on its way collecting data. You need to have a browser to interact
with in order to do your part.

Install
-------

You'll need to install [ChromeDriver] before doing anything else. If you use
Homebrew on OS X this is as easy as:

    brew cask install chromedriver

Then you'll want to install [Python 3] and:

    pip3 install etudier

Run
---

To use étudier you first need to navigate to a page on Google Scholar that you are
interested in, for example here is the page of citations that reference Sherry
Ortner's [Theory in Anthropology since the Sixties]. Then you start *etudier* up
pointed at that page.

    % etudier 'https://scholar.google.com/scholar?start=0&hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc='

If you are interested in starting with keyword search results in Google Scholar
you can do that too. For example here is the url for searching for "cscw memory"
if I was interested in papers that talk about the CSCW conference and memory:

    % etudier 'https://scholar.google.com/scholar?hl=en&as_sdt=0%2C21&q=cscw+memory&btnG='

Note: it's important to quote the URL so that the shell doesn't interpret the
ampersands as an attempt to background the process.

### --pages

By default *étudier* will collect the 10 citations on that page and then look at
the top 10 citations that reference each one. So you will end up with no more
than 100 citations being collected (10 on each page * 10 citations).

If you would like to get more than one page of results use the `--pages`. For
example this would result in no more than 400 (20 * 20) results being collected:

    % etudier --pages 2 'https://scholar.google.com/scholar?start=0&hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc=' 

### --depth

And finally if you would like to look at the citations of the citations you use the
--depth parameter. 

    % etudier --depth 2 'https://scholar.google.com/scholar?start=0&hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc='

This will collect the initial set of 10 citations, the top 10 citations for
each, and then the top 10 citations of each of those, so no more than 1000
citations 1000 citations (10 * 10 * 10). It's no more because there is certain
to be some cross-citation duplication.

### --output

By default `output.gexf`, `output.graphml` and `output.html` files will be
written to the current working directory, but you can change this with the
`--output` option to control the prefix that is used. The output file will
contain rudimentary metadata collected from Google Scholar including:

- *id* - the cluster identifier assigned by Google
- *url* - the url for the publication
- *title* - the title of the publication
- *authors* - a comma separated list of the publication authors
- *year* - the year of publication
- *cited-by* - the number of other publications that cite the publication
- *cited-by-url* - a Google Scholar URL for the list of citing publications
* modularity - the modularity value obtained from community detection

Features of HTML/D3 output
--------------------------

- Node's color shows its citation group
- Node's size shows its times being cited
- Click node to open its source website
- Dragable nodes
- Zoom and pan
- Double-click to center node
- Resizable window
- Text labels
- Hover to highlight 1st-order neighborhood
- Click and press node to fade surroundings

[Theory in Anthropology since the Sixties]: https://scholar.google.com/scholar?hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc=
[Google Scholar]: https://scholar.google.com
[Selenium]: https://docs.seleniumhq.org/
[requests-html]: http://html.python-requests.org/
[quite protective]: https://www.quora.com/Are-there-technological-or-logistical-challenges-that-explain-why-Google-does-not-have-an-official-API-for-Google-Scholar
[GEXF]: https://gephi.org/
[GraphML]: https://networkx.org/documentation/stable/reference/readwrite/graphml.html
[networkx]: https://networkx.github.io/
[D3]: https://d3js.org/
[Python 3]: https://www.python.org/downloads/
[ChromeDriver]: https://sites.google.com/chromium.org/driver/
