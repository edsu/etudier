<img height=200 src="https://raw.githubusercontent.com/edsu/etudier/master/example/output.png">

*étudier* will drive a (non-headless) browser to collect a citation graph from
Google Scholar. It's non-headless because Google is very protective of this data
and routinely will ask you to solve a captcha (identifying street signs, cars,
etc in photos). *étudier* will allow you to complete these tasks when they occur
and then will continue on its way collecting data.

Currently it outputs a GEXF file that you can load into Gephi.

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
