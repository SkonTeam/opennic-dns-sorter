import urllib.request
import datetime
import os
import sys
import subprocess, platform
import re
import argparse

# https://stackoverflow.com/questions/2953462/pinging-servers-in-python
def ping(host):
    """
    Returns True if host responds to a ping request
    """
    # Ping parameters as function of OS
    ping_str = "-n 1" if  platform.system().lower()=="windows" else "-c 1"
    args = "ping " + " " + ping_str + " " + host
    need_sh = False if  platform.system().lower()=="windows" else True

    try:
    	# Ping
    	ping_output = subprocess.check_output(args, shell=need_sh)
    except Exception as e:
    	return 0

    latency = get_ping_latency(ping_output.decode("utf-8"))
    try:
    	return int(latency)
    except ValueError:
    	return 0

def get_ping_latency(stdoutput):
	m = re.search('(?<=time=)\d+',stdoutput)
	return m.group(0)

# Function from : https://gist.github.com/vladignatyev/06860ec2040cb497f0f3
def progress(count, total, status=''):
	bar_len = 60
	filled_len = int(round(bar_len * count / float(total)))

	percents = round(100.0 * count / float(total), 1)
	bar = '#' * filled_len + '-' * (bar_len - filled_len)

	sys.stdout.write('[%s] %s%s %s\r' % (bar, percents, '%', status))
	sys.stdout.flush() # As suggested by Rom Ruben (see: http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console/27871113#comment50529068_27871113)

class DnsServer():
	"""docstring for DnsServer"""
	def __init__(self, ip):
		self.ip = ip.strip()
		self.meanLatency = 0
		self.lastLetency = 0
	
	def __str__(self):
		row_format = "{:>15}" * 3
		meanToPrint = "mean=" + str(self.meanLatency) + "ms"
		lastToPrint = "last=" + str(self.lastLetency) + "ms"
		return row_format.format(self.ip,meanToPrint,lastToPrint)

	def ping(self,tries):
		tries = 1 if tries==0 else tries
		latencySum = 0
		for x in range(0,tries):
			latency = ping(self.ip)
			latencySum = latencySum + latency
		self.meanLatency = latencySum / tries
		self.lastLetency = latency

class DnsServerPool():
	"""docstring for DnsServerPool"""
	def __init__(self):
		self.pool = []

	def add_server(self,ip):
		dnsObj = DnsServer(ip)
		self.pool.append(dnsObj)
	
	def ping(self,tries):
		i = 1
		for dns in self.pool:
			#print("[" + str(i) +"/" + str(len(self.pool)) +"] " +"Pinging : " + dns.ip)
			progress(i,len(self.pool),dns.ip)
			dns.ping(tries)
			i = i+1
		sys.stdout.flush()			
	
	# Sorts servers from fastest to slowest
	def sort(self):
		self.pool.sort(key=lambda x:x.meanLatency)

	def view(self,n=999):
		n = n if n < len(self.pool) else len(self.pool)
		for dns in self.pool[:n]:
			print(dns)

	def save(self,filename):
		with open(filename,"w") as f:
			for dns in self.pool:
				lineToWrite = dns.ip + "," + str(dns.meanLatency) + "," + str(dns.lastLetency) +"\n"
				f.write(lineToWrite)
	
	def load(self,filename):
		with open(filename,"r") as f:
			for line in f:
				ip = line.split(",")[0]
				mean = line.split(",")[1]
				last = line.split(",")[2]
				dnsServer = DnsServer(ip)
				dnsServer.meanLatency = float(mean)
				dnsServer.lastLetency = int(last)
				self.pool.append(dnsServer)
	
	# Omits 0ms latency servers from the pool
	def cleanup_pool(self):
		pool_backup = self.pool
		self.pool = [dns for dns in self.pool if dns.meanLatency != 0]
		if len(self.pool) == 0:
			self.pool = pool_backup
	
	def as_ip_list(self):
		return [dns.ip for dns in self.pool]



		
def get_opennic_dns_report():
	r = urllib.request.urlopen("http://report.opennicproject.org/files/t2report.txt").read()
	return r.decode("utf-8")

# Not all the servers are present through this API
def get_opennic_dns_geoip():
	r = urllib.request.urlopen("https://api.opennicproject.org/geoip/?bare&wl&bl&pct=1&res=999").read()
	return r.decode("utf-8")

def get_report_date(report):
	dateLine = report.splitlines()[2]
	dateStr = dateLine.split("--")[0].strip()
	parsedDate = datetime.datetime.strptime(dateStr,"%Y %b %d, %H:%M %Z")
	return parsedDate.strftime("%Y%m%d")

def get_dns_report(force=False):
	today = datetime.datetime.now()
	filename = "dns-report-" + today.strftime("%Y%m%d") + ".txt"
	if not os.path.isfile(filename) or force == True:		
		report = get_opennic_dns_report()
		f = open(filename,"w")
		f.write(report)
		f.close()
	else:
		f = open(filename,"r")
		report = f.read()
		f.close()
	return report,filename

def isDnsEntryLine(line):
	# TMP: excludes IPV6 dns servers.
	return not line.startswith('-') and "@" in line and ":" not in line

def get_dns_from_line(line):
	return line.split(" @ ")[1]

def parse_report(report,dns_pool):
	with open(report,"r") as f:
		for line in f:
			if isDnsEntryLine(line):
				dnsip = get_dns_from_line(line).strip()
				dns_pool.add_server(dnsip)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Find best OpenNIC tier 2 DNS servers')
	parser.add_argument('-n',type=int,default=4,help='number of pings to send per server (default: 4)')
	parser.add_argument('-t',type=int,default=10,help='number of servers to show (default: 10)')
	parser.add_argument('-f',action='store_true',help='force list refetch and bypasses saved results')
	args = parser.parse_args()

	tries = args.n
	force = args.f
	top = args.t

	today = datetime.datetime.now()
	saveFilename = "dns-" + today.strftime("%Y%m%d") + ".txt"
	
	dns_pool = DnsServerPool()
	if os.path.isfile(saveFilename) and not force:
		dns_pool.load(saveFilename)
		dns_pool.sort()
		dns_pool.cleanup_pool()
		dns_pool.view(top)
	else:
		dns_report,filename = get_dns_report(force)
		parse_report(filename,dns_pool)
		dns_pool.ping(tries)
		dns_pool.sort()
		dns_pool.save(saveFilename)
		dns_pool.cleanup_pool()
		dns_pool.view(top)

