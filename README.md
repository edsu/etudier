<img style="float: left;" height=300 src="https://raw.githubusercontent.com/edsu/etudier/master/example/output.png">

*étudier* is a small Python program that uses [Selenium] and [requests-html] to
drive a (non-headless) browser to collect a citation graph around a particular
citation from [Google Scholar] and write it out as a [Gephi] file using
[networkx].

If you are wondering why it uses a non-headless it's because Google is [quite
protective] of this data and routinely will ask you to solve a captcha
(identifying street signs, cars, etc in photos).  *étudier* will allow you to
complete these tasks when they occur and then will continue on its way
collecting data.

### Install

You'll need to install [ChromeDriver] before doing anything else. If you use
Homebrew on OS X this is as easy as:

    brew install chromedriver

Then you'll want to install Python3 and:

    pip3 install etudier

Now you should be ready:

### Run

To use it you first need to navigate to a page on Google Scholar that you are
interested, for example here is the page of citations that reference Sherry
Ortner's [Theory in Anthropology since the Sixties]. Then you start *etudier* up
pointed at that page.

./etudier.py 'https://scholar.google.com/scholar?start=0&hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc='

### --pages

By default *étudier* will collect the 10 citations on that page and then look at
the top 10 citatations that reference each one. So you will end up with no more
than 100 citations being collected (10 on each page * 10 citations).

If you would like to get more than one page of results use the `--pages`. For
example this would result in no more than 400 (20 * 20) results being collected:

./etudier.py 'https://scholar.google.com/scholar?start=0&hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc=' --pages 2

### --depth

And finally if you would like to look at the citations of the citations you the
--depth parameter. 

'https://scholar.google.com/scholar?start=0&hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc= --depth=2

This will collect the initial set of 10 citations, the top 10 citations for
each, and then the top 10 citations of each, so no more than 1000 citations 1000
citations (10 * 10 * 10). It's no more because there is certain to be some
duplication of publications in the citations of each.

### --output

By default a file called `output.gexf` will be written, but you can change this
with the `--output` option. The output file will contain rudimentary metadata
collected from Google Scholar including:

- *id* - the cluster identifier assigned by Google
- *url* - the url for the publication
- *title* - the title of the publication
- *authors* - a comma separated list of the publication authors
- *year* - the year of publication
- *cited-by* - the number of other publications that cite the publication
- *cited-by-url* - a Google Scholar URL for the list of citing publications

[Theory in Anthropology since the Sixties]: https://scholar.google.com/scholar?hl=en&as_sdt=20000005&sciodt=0,21&cites=17950649785549691519&scipsc=
[Google Scholar]: https://scholar.google.com
[Selenium]: https://docs.seleniumhq.org/
[requests-html]: http://html.python-requests.org/
[quite protective]: https://www.quora.com/Are-there-technological-or-logistical-challenges-that-explain-why-Google-does-not-have-an-official-API-for-Google-Scholar
[Gephi]: https://gephi.org/
[networkx]: https://networkx.github.io/
