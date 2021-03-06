#!/usr/bin/env python

""" 
Integration of TFA Dostmann 'AirCO2ntrol Mini' CO2 Monitor into OpenHAB. 
Adapted from https://hackaday.io/project/5301-reverse-engineering-a-low-cost-usb-co-monitor/log/17909-all-your-base-are-belong-to-us
March 2016 - Kristof Robot
"""

import sys, fcntl, time, requests, base64

def basic_header():
    """ Header for OpenHAB REST request - standard """
    auth = base64.encodestring('%s:%s'
                       %("", "")
                       ).replace('\n', '')
    return {
            "Authorization" : "Basic %s" %auth,
            "Content-type": "text/plain"}

def decrypt(key,  data):
    cstate = [0x48,  0x74,  0x65,  0x6D,  0x70,  0x39,  0x39,  0x65]
    shuffle = [2, 4, 0, 7, 1, 6, 5, 3]
    
    phase1 = [0] * 8
    for i, o in enumerate(shuffle):
        phase1[o] = data[i]
    
    phase2 = [0] * 8
    for i in range(8):
        phase2[i] = phase1[i] ^ key[i]
    
    phase3 = [0] * 8
    for i in range(8):
        phase3[i] = ( (phase2[i] >> 3) | (phase2[ (i-1+8)%8 ] << 5) ) & 0xff
    
    ctmp = [0] * 8
    for i in range(8):
        ctmp[i] = ( (cstate[i] >> 4) | (cstate[i]<<4) ) & 0xff
    
    out = [0] * 8
    for i in range(8):
        out[i] = (0x100 + phase3[i] - ctmp[i]) & 0xff
    
    return out

def hd(d):
    return " ".join("%02X" % e for e in d)

def publish_openhab_status(key, value):
    """ Put a status update to OpenHAB  key is item, value is state """
    url = 'http://localhost:8080/rest/items/%s/state'%(key)
    try:
        req = requests.put(url, data=value, headers=basic_header())
    except:
        #Ignore connection errors
        pass
#    if req.status_code != requests.codes.ok:
#        req.raise_for_status()

if __name__ == "__main__":
    # Key retrieved from /dev/random, guaranteed to be random ;)
    key = [0xc4, 0xc6, 0xc0, 0x92, 0x40, 0x23, 0xdc, 0x96]
    
    fp = open(sys.argv[1], "a+b",  0)
    
    HIDIOCSFEATURE_9 = 0xC0094806
    set_report = "\x00" + "".join(chr(e) for e in key)
    fcntl.ioctl(fp, HIDIOCSFEATURE_9, set_report)
    
    values = {}
    lastTemp = 0
    lastCO2 = 0
    
    while True:
        data = list(ord(e) for e in fp.read(8))
        decrypted = decrypt(key, data)
        if decrypted[4] != 0x0d or (sum(decrypted[:3]) & 0xff) != decrypted[3]:
            print hd(data), " => ", hd(decrypted),  "Checksum error"
        else:
            op = decrypted[0]
            val = decrypted[1] << 8 | decrypted[2]
            
            values[op] = val
            
            # Output all data, mark just received value with asterisk
            #print ", ".join( "%s%02X: %04X %5i" % ([" ", "*"][op==k], k, v, v) for (k, v) in sorted(values.items())), "  ", 
            ## From http://co2meters.com/Documentation/AppNotes/AN146-RAD-0401-serial-communication.pdf
            if 0x50 in values and lastCO2 != values[0x50]:
                print "CO2: %4i" % values[0x50]
                publish_openhab_status("CO2", str(values[0x50]))
                lastCO2 = values[0x50]
            if 0x42 in values and lastTemp != values[0x42]:
                print "T: %2.2f" % (values[0x42]/16.0-273.15)
                publish_openhab_status("CO2_T","%.2f" % (values[0x42]/16.0-273.15))
                lastTemp = values[0x42]
            #if 0x44 in values:
                #print "RH: %2.2f" % (values[0x44]/100.0), 
            #print
