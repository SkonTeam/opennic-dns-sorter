# opennic-dns-sorter
Find best OpenNIC tier 2 DNS servers
## Usage
`python opennic-dns-sorter.py`

for other options check the help `--help`
Also by default it sends 4 ping requests, if you want to speed the test up pass in `-n 1` to trim it down to 1 ping per server although you should know that it my not be as accurate.