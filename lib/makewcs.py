"""
MAKEWCS.PY - Updated the WCS in an image header so that
            it matches the geometric distortion defined in an IDC table
            which is referenced in the image header.

This version tries to implement a full updating of the WCS based on
information about the V2/V3 plane which is obtained from th IDCTAB and,
in the case of WFPC2, the OFFTAB.

The only parameters from the original WCS which are retained are
the CRVALs of the reference chip.

The original WCS are first copied to MCD1_1 etc before being updated.

UPINCD history:
First try, Richard Hook, ST-ECF/STScI, August 2002.
Version 0.0.1 (WJH) - Obtain IDCTAB using PyDrizzle function.
Version 0.1 (WJH) - Added support for processing image lists.  
                    Revised to base CD matrix on ORIENTAT, instead of PA_V3
                    Supports subarrays by shifting coefficients as needed.
Version 0.2 (WJH) - Implemented orientation computation based on PA_V3 using
                    Troll function from Colin to compute new ORIENTAT value.
Version 0.3 (WJH) - Supported filter dependent distortion models in IDCTAB
                    fixed bugs in applying Troll function to WCS.
Version 0.4 (WJH) - Updated to support use of 'defaultModel' for generic 
                    cases: XREF/YREF defaults to image center and idctab
                    name defaults to None.
Version 0.5 (WJH) - Added support for WFPC2 OFFTAB updates, which updates
                    the CRVALs.  However, for WFPC2 data, the creation of
                    the backup values does not currently work.
---------------------------
MAKEWCS V0.0 (RNH) - Created new version to implement more complete
                     WCS creation based on a reference tangent plane.

        V0.1 (RNH) - First working version for tests. May 20th 2004.
        V0.11 (RNH) - changed reference chip for ACS/WFC. May 26th 2004.
        V0.2 (WJH) - Removed all dependencies from IRAF and use new WCSObject
                    class for all WCS operations.
        V0.4 (WJH/CJH) - Corrected logic for looping of extension in FITS image.
        V0.5 (RNH) - Chip to chip CRVAL shifting logic change.
        V0.6 (CJH/WJH) - Added support for non-associated STIS data.
        V0.6.2 (WJH) - Added support for NICMOS data. This required
                        new versions of wcsutil and fileutil in PyDrizzle.
        V0.6.3 (WJH) - Modified to support new version of WCSUtil which correctly
                        sets up and uses archived WCS keywords.
        
"""

#import iraf
from math import *
import string
import pydrizzle
#from WCS import WCS

from pydrizzle import wcsutil,fileutil,drutil,buildasn

import numarray as N

yes = True
no = False

# Define parity matrices for supported detectors.
# These provide conversion from XY to V2/V3 coordinate systems.
# Ideally, this information could be included in IDCTAB...
PARITY = {'WFC':[[1.0,0.0],[0.0,-1.0]],'HRC':[[-1.0,0.0],[0.0,1.0]],
          'SBC':[[-1.0,0.0],[0.0,1.0]],'default':[[1.0,0.0],[0.0,1.0]],
          'WFPC2':[[-1.0,0.],[0.,1.0]],'STIS':[[-1.0,0.],[0.,1.0]],
          'NICMOS':[[-1.0,0.],[0.,1.0]]}

NUM_PER_EXTN = {'ACS':3,'WFPC2':1,'STIS':3,'NICMOS':5}

__version__ = '0.6.3 (24 January 2005)'
def run(image,quiet=yes,restore=no,prepend='O'):

    print "+ MAKEWCS Version %s" % __version__
    
    _prepend = prepend
    
    if image.find('[') > -1:
        # We were told to only work with a specific extension
        if restore == no:
            # First get the name of the IDC table
            idctab = drutil.getIDCFile(image,keyword='idctab')[0]
            _found = fileutil.findFile(idctab)
            if idctab == None or idctab == '':
                print '#\n No IDCTAB specified.  No correction can be done. Quitting...\n#\n'
                return
            elif not _found:
                print '#\n IDCTAB: ',idctab,' could not be found. Quitting...\n#\n'
                return

            _update(image,idctab,quiet=quiet,prepend=_prepend)
        else: 
            if not quiet:
                print 'Restoring original WCS values for',image  
            restoreCD(image,_prepend)
    else:
        # Work with all extensions of all images in list    
        _files = buildasn._findFiles(image)
        if not quiet:
            print "_files: ",_files

        # First get the name of the IDC table
        idctab = drutil.getIDCFile(_files[0][0],keyword='idctab')[0]
        _found = fileutil.findFile(idctab)
        if idctab == None or idctab == '':
            print '#\n No IDCTAB specified.  No correction can be done. Quitting...\n#\n'
            return
        elif not _found:
            print '#\n IDCTAB: ',idctab,' could not be found. Quitting...\n#\n'
            return

        for img in _files:
            _phdu = img[0]+'[0]'
            _numext = int(drutil.findNumExt(_phdu))
            _instrument = fileutil.getKeyword(_phdu,keyword='INSTRUME')

            if NUM_PER_EXTN.has_key(_instrument):
                _num_per_extn = NUM_PER_EXTN[_instrument]
            else:
                raise "Instrument %s not supported yet. Exiting..."%_instrument
                            
            _nimsets = _numext / _num_per_extn
            for i in xrange(_nimsets):
                if img[0].find('.fits') > 0:
                    _image = img[0]+'[sci,'+repr(i+1)+']'
                else:
                    _image = img[0]+'['+repr(i+1)+']'

                if not restore:
                    _update(_image,idctab, quiet=quiet,instrument=_instrument,prepend=_prepend)
                else:                    
                    if not quiet:
                        print 'Restoring original WCS values for',_image  
                    restoreCD(_image,_prepend)

def restoreCD(image,prepend):
    
    _prepend = prepend
    try:
        _wcs = wcsutil.WCSObject(image)
        _wcs.restoreWCS(prepend=_prepend)
        del _wcs
    except: 
        print 'ERROR: Could not restore WCS keywords for %s.'%image

def _update(image,idctab,quiet=None,instrument=None,prepend=None):
    
    _prepend = prepend
    
    # Check to see whether we are working with GEIS or FITS input
    _fname,_iextn = fileutil.parseFilename(image)
    
    if _fname.find('.fits') < 0:
        # Input image is NOT a FITS file, so 
        #     build a FITS name for it's copy.
        _fitsname = fileutil.buildFITSName(_fname)
    else:
        _fitsname = None
    
    # Try to get the instrument if we don't have it already
    instrument = fileutil.getKeyword(image,'INSTRUME')

    # Read in any specified OFFTAB, if present (WFPC2)
    offtab = fileutil.getKeyword(image,'OFFTAB')
    dateobs = fileutil.getKeyword(image,'DATE-OBS')
    if not quiet:
        print "OFFTAB, DATE-OBS: ",offtab,dateobs

    # Get the original image WCS
    Old=wcsutil.WCSObject(image,prefix=_prepend)
    # Reset the WCS keywords to original archived values.
    Old.restore()

    print "-Updating image ",image

    if not quiet:
        print "-Reading IDCTAB file ",idctab

    # Get telescope orientation from image header
    pvt = float(fileutil.getKeyword(image,'PA_V3'))
     
    # Find out about instrument, detector & filters
    detector = fileutil.getKeyword(image,'DETECTOR')

    Nrefchip=1
    if instrument == 'WFPC2':
        filter1 = fileutil.getKeyword(image,'FILTNAM1')
        filter2 = fileutil.getKeyword(image,'FILTNAM2')
        Nrefchip=3
    elif instrument == 'NICMOS':
        filter1 = fileutil.getKeyword(image,'FILTER')
        filter2 = None
    else:
        filter1 = fileutil.getKeyword(image,'FILTER1')
        filter2 = fileutil.getKeyword(image,'FILTER2')
    
    # For the ACS/WFC case the chip number doesn't match the image
    # extension
    if instrument == 'ACS' and detector == 'WFC':
       Nrefchip = 2
       nr = 1
    elif instrument == 'NICMOS':
        Nrefchip = fileutil.getKeyword(image,'CAMERA')
        nr = 1
    else:
       nr = Nrefchip

    # Create the reference image name
    rimage = image.split('[')[0]+"[%d]" % nr
    if not quiet:
       print "Reference image: ",rimage

    # Read in declination of target (for computing orientation at aperture)
    # Note that this is from the reference image
    dec = float(fileutil.getKeyword(rimage,'CRVAL2'))
    crval1 = float(fileutil.getKeyword(rimage,'CRVAL1'))
    crval2 = dec

    if filter1 == None or filter1.strip() == '': filter1 = 'CLEAR'
    else: filter1 = filter1.strip()
    if filter2 == None or filter2.strip() == '': filter2 = 'CLEAR'
    else: filter2 = filter2.strip()
    
    if filter1.find('CLEAR') == 0: filter1 = 'CLEAR'
    if filter2.find('CLEAR') == 0: filter2 = 'CLEAR'
    
    # Set up parity matrix for chip
    if instrument == 'WFPC2' or instrument =='STIS' or instrument == 'NICMOS':
        parity = PARITY[instrument]
    elif PARITY.has_key(detector):
       parity = PARITY[detector]
    else:
        raise 'Detector ',detector,' Not supported at this time. Exiting...'

    # If ACS get the VAFACTOR, otherwise set to 1.0
    # we also need the reference pointing position of the target
    # as this is where
    VA_fac=1.0
    if instrument == 'ACS':
       VA_fac = float(fileutil.getKeyword(image,'VAFACTOR'))
       if not quiet:
          print 'VA factor: ',VA_fac
       
    ra_targ = float(fileutil.getKeyword(image,'RA_TARG'))
    dec_targ = float(fileutil.getKeyword(image,'DEC_TARG'))

    # Get the chip number
    _c = fileutil.getKeyword(image,'CAMERA')
    _s = fileutil.getKeyword(image,'CCDCHIP')
    _d = fileutil.getKeyword(image,'DETECTOR')
    if _c != None and str(_c).isdigit():
        chip = int(_c)
    elif _s == None and _d == None:
        chip = 1
    else:
        if _s:
            chip = int(_s)
        elif str(_d).isdigit():
            chip = int(_d)
        else:
            chip = 1

    if not quiet:
        print "-PA_V3 : ",pvt," CHIP #",chip

    # Extract the appropriate information from the IDCTAB
    fx,fy,refpix,order=fileutil.readIDCtab(idctab,chip=chip,direction='forward',
                filter1=filter1,filter2=filter2,offtab=offtab,date=dateobs)

    # Extract the appropriate information for reference chip
    rfx,rfy,rrefpix,rorder=fileutil.readIDCtab(idctab,chip=Nrefchip,
        direction='forward', filter1=filter1,filter2=filter2,offtab=offtab, 
        date=dateobs)

    # Convert the PA_V3 orientation to the orientation at the aperture
    # This is for the reference chip only - we use this for the
    # reference tangent plane definition
    # It has the same orientation as the reference chip
    pv = wcsutil.troll(pvt,dec,rrefpix['V2REF'],rrefpix['V3REF'])

    # Add the chip rotation angle
    if rrefpix['THETA']:
       pv += rrefpix['THETA']

    # Create the tangent plane WCS on which the images are defined
    # This is close to that of the reference chip
    R=wcsutil.WCSObject(rimage)

    # Get an approximate reference position on the sky
    crval1,crval2=R.xy2rd((rrefpix['XREF'],rrefpix['YREF']))

    # Set values for the rest of the reference WCS
    R.crval1=crval1
    R.crval2=crval2
    R.crpix1=0.0
    R.crpix2=0.0
    R_scale=rrefpix['PSCALE']/3600.0
    R.cd11=parity[0][0] *  cos(pv*pi/180.0)*R_scale
    R.cd12=parity[0][0] * -sin(pv*pi/180.0)*R_scale
    R.cd21=parity[1][1] *  sin(pv*pi/180.0)*R_scale
    R.cd22=parity[1][1] *  cos(pv*pi/180.0)*R_scale

    if not quiet:
        print "  Reference Chip Scale (arcsec/pix): ",rrefpix['PSCALE']

    # Offset and angle in V2/V3 from reference chip to
    # new chip(s) - converted to reference image pixels
    v2=refpix['V2REF']
    v3=refpix['V3REF']
    v2ref=rrefpix['V2REF']
    v3ref=rrefpix['V3REF']

    off = sqrt((v2-v2ref)**2 + (v3-v3ref)**2)/(R_scale*3600.0)

    # Here we must include the PARITY
    if v3 == v3ref:
       theta=0.0
    else:
       theta = atan2(parity[0][0]*(v2-v2ref),parity[1][1]*(v3-v3ref))

    if rrefpix['THETA']: theta += rrefpix['THETA']*pi/180.0

    dX=off*sin(theta)
    dY=off*cos(theta)

    # Create a new instance of a WCS
    if _fitsname == None:
        _new_name = image
    else:
        _new_name = _fitsname+'['+str(_iextn)+']'

    #New=wcsutil.WCSObject(_new_name)
    New = Old.copy()

    # Calculate new CRVALs and CRPIXs
    New.crval1,New.crval2=R.xy2rd((dX,dY))
    New.crpix1=refpix['XREF']
    New.crpix2=refpix['YREF']

    # Angle of chip relative to chip
    if refpix['THETA']:
       dtheta = refpix['THETA'] - rrefpix['THETA']
    else:
       dtheta = 0.0

    # Create a small vector, in reference image pixel scale
    # There is no parity effect here ???
    delXX=fx[1,1]/R_scale/3600.
    delYX=fy[1,1]/R_scale/3600.
    delXY=fx[1,0]/R_scale/3600.
    delYY=fy[1,0]/R_scale/3600.

    # Convert to radians
    rr=dtheta*pi/180.0

    # Rotate the vectors
    dXX= cos(rr)*delXX - sin(rr)*delYX
    dYX= sin(rr)*delXX + cos(rr)*delYX

    dXY= cos(rr)*delXY - sin(rr)*delYY
    dYY= sin(rr)*delXY + cos(rr)*delYY

    # Transform to sky coordinates
    a,b=R.xy2rd((dX+dXX,dY+dYX))
    c,d=R.xy2rd((dX+dXY,dY+dYY))

    # Calculate the new CDs and convert to degrees
    New.cd11=diff_angles(a,New.crval1)*cos(New.crval2*pi/180.0)
    New.cd12=diff_angles(c,New.crval1)*cos(New.crval2*pi/180.0)
    New.cd21=diff_angles(b,New.crval2)
    New.cd22=diff_angles(d,New.crval2)

    # Apply the velocity aberration effect if applicable
    if VA_fac != 1.0:

       # First shift the CRVALs apart
#       New.crval1 = ra_targ + VA_fac*(New.crval1 - ra_targ) 
#       New.crval2 = dec_targ + VA_fac*(New.crval2 - dec_targ) 
       # First shift the CRVALs apart
       # This is now relative to the reference chip, not the
       # target position.
       New.crval1 = R.crval1 + VA_fac*diff_angles(New.crval1, R.crval1)
       New.crval2 = R.crval2 + VA_fac*diff_angles(New.crval2, R.crval2)

       # and scale the CDs
       New.cd11 = New.cd11*VA_fac
       New.cd12 = New.cd12*VA_fac
       New.cd21 = New.cd21*VA_fac
       New.cd22 = New.cd22*VA_fac

    # Store new one
    # archive=yes specifies to also write out archived WCS keywords
    # overwrite=no specifies do not overwrite any pre-existing archived keywords
    New.write(fitsname=_new_name,overwrite=no,quiet=quiet,archive=yes)
    
    """ Convert distortion coefficients into SIP style
        values and write out to image (assumed to be FITS). 
    """   
    #First the CD matrix:
    f = refpix['PSCALE']/3600.0
    a = fx[1,1]/3600.0
    b = fx[1,0]/3600.0
    c = fy[1,1]/3600.0
    d = fy[1,0]/3600.0
    det = (a*d - b*c)*refpix['PSCALE']
    
    # Write to header
    fimg = fileutil.openImage(_new_name,mode='update')
    _new_root,_nextn = fileutil.parseFilename(_new_name)
    _new_extn = fileutil.getExtn(fimg,_nextn)
    
    # Transform the higher-order coefficients
    for n in range(order+1):
      for m in range(order+1):
        if n >= m and n>=2:

          # Form SIP-style keyword names
          Akey="A_%d_%d" % (m,n-m)
          Bkey="B_%d_%d" % (m,n-m)

          # Assign them values
          #Aval=string.upper("%13.9e" % (f*(d*fx[n,m]-b*fy[n,m])/det))
          #Bval=string.upper("%13.9e" % (f*(a*fy[n,m]-c*fx[n,m])/det))
          Aval= f*(d*fx[n,m]-b*fy[n,m])/det
          Bval= f*(a*fy[n,m]-c*fx[n,m])/det
          
          _new_extn.header.update(Akey,Aval)
          _new_extn.header.update(Bkey,Bval)

    # Update the SIP flag keywords as well
    #iraf.hedit(image,"CTYPE1","RA---TAN-SIP",verify=no,show=no)
    #iraf.hedit(image,"CTYPE2","DEC--TAN-SIP",verify=no,show=no)
    #fimg[_extn].header.update("CTYPE1","RA---TAN-SIP")
    #fimg[_extn].header.update("CTYPE2","DEC--TAN-SIP")

    # Finally we also need the order
    #iraf.hedit(image,"A_ORDER","%d" % order,add=yes,verify=no,show=no)
    #iraf.hedit(image,"B_ORDER","%d" % order,add=yes,verify=no,show=no)
    _new_extn.header.update("A_ORDER",order)
    _new_extn.header.update("B_ORDER",order)
    
    # Close image now
    fimg.close()
    del fimg
    

def diff_angles(a,b):
    """ Perform angle subtraction a-b taking into account
        small-angle differences across 360degree line. """
        
    diff = a - b

    if diff > 180.0:
       diff -= 360.0

    if diff < -180.0:
       diff += 360.0
    
    return diff
     
def shift_coeffs(cx,cy,xs,ys,norder):
    """
    Shift reference position of coefficients to new center 
    where (xs,ys) = old-reference-position - subarray/image center.
    This will support creating coeffs files for drizzle which will 
    be applied relative to the center of the image, rather than relative
    to the reference position of the chip.
    
    Derived directly from PyDrizzle V3.3d.
    """

    _cxs = N.zeros(shape=cx.shape,type=cx.type())
    _cys = N.zeros(shape=cy.shape,type=cy.type())
    _k = norder + 1

    # loop over each input coefficient
    for m in xrange(_k):
        for n in xrange(_k):
            if m >= n:
                # For this coefficient, shift by xs/ys.
                _ilist = N.array(range(_k - m)) + m
                # sum from m to k
                for i in _ilist:
                    _jlist = N.array(range( i - (m-n) - n + 1)) + n
                    # sum from n to i-(m-n)
                    for j in _jlist:
                        _cxs[m,n] = _cxs[m,n] + cx[i,j]*pydrizzle._combin(j,n)*pydrizzle._combin((i-j),(m-n))*pow(xs,(j-n))*pow(ys,((i-j)-(m-n)))
                        _cys[m,n] = _cys[m,n] + cy[i,j]*pydrizzle._combin(j,n)*pydrizzle._combin((i-j),(m-n))*pow(xs,(j-n))*pow(ys,((i-j)-(m-n)))
    _cxs[0,0] = _cxs[0,0] - xs
    _cys[0,0] = _cys[0,0] - ys
    #_cxs[0,0] = 0.
    #_cys[0,0] = 0.

    return _cxs,_cys
        
def help():
    _help_str = """ makewcs - a task for updating an image header WCS to make
          it consistent with the distortion model and velocity aberration.  
    
    This task will read in a distortion model from the IDCTAB and generate 
    a new WCS matrix based on the value of ORIENTAT.  It will support subarrays
    by shifting the distortion coefficients to image reference position before
    applying them to create the new WCS, including velocity aberration. 
    Original WCS values will be moved to an O* keywords (OCD1_1,...).
    Currently, this task will only support ACS and WFPC2 observations.
    
    Syntax:
        makewcs.run(image,quiet=no)
    where 
        image   - either a single image with extension specified,
                  or a substring common to all desired image names,
                  or a wildcarded filename
                  or '@file' where file is a file containing a list of images
        quiet   - turns off ALL reporting messages: 'yes' or 'no'(default)
        restore - restore WCS for all input images to defaults if possible:
                    'yes' or 'no'(default) 
    Usage:
        --> import makewcs
        --> makewcs.run('raw') # This will update all _raw files in directory
        --> makewcs.run('j8gl03igq_raw.fits[sci,1]')
    """
    print _help_str