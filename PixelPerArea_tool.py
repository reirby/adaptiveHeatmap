# This script tool is designed to produce a heat map of spatially distributed
# phenomena (plants on a crop field).
# This tool takes a bianry raster, where pixesl of interest have values of 1
# and all other pixels are 'no data', and then crates a network, adjusted to the distribution
# of the object of interest. The output of the tool is a heatmap raster, showing pixel
# per square meter count.

#Andrei Kushkin
#december 2014

import arcpy
import os
arcpy.env.overwriteOutput = True
arcpy.CheckOutExtension("Spatial")

# -------------------------parameters---------------------

#input raster
inR = arcpy.GetParameterAsText(0)
#output folder
arcpy.env.workspace =  arcpy.GetParameterAsText(1)
#output name
outRst =os.path.basename(inR) + '_heatmap.tif' 

#raster sell size and extent.  get from input raster
rCllSz = arcpy.GetRasterProperties_management(inR, 'CELLSIZEX')

#Fishnet parameters
#fishnet size
fnS = arcpy.GetParameterAsText(2)
if fnS !='':
    fnS= float(fnS)
else:
    fnS = 1
#origin_coord
origin_coordY = arcpy.GetRasterProperties_management (inR, 'TOP')
origin_coordX = arcpy.GetRasterProperties_management (inR, 'LEFT')
oc_coordY = arcpy.GetRasterProperties_management (inR, 'BOTTOM')
oc_coordX = arcpy.GetRasterProperties_management (inR, 'RIGHT')

origin_coord = str(origin_coordX)+' '+str(oc_coordY) #Left+bottom
axY_coord = str(origin_coordX)+' '+str(float(str(oc_coordY))+10)
oc_coord = str(oc_coordX)+' '+str(origin_coordY) #right+top
#print origin_coordY #top
#print origin_coordX #left
#print'-------'
#print oc_coordY #bottom
#print oc_coordX #right
#print axY_coord
#print 'origin coord: '+ origin_coord
#print 'opposite corner: '+ oc_coord
#print 'Y-axis coord: '+ axY_coord

#polygon size threshold (for filtering too small polys)
pT= arcpy.GetParameterAsText(3)
if pT !='':
    pT= float(pT)
else:
    pT= 0.1


#Area_Units 
aU= arcpy.GetParameterAsText(4)
if aU !='':
    aU=aU
else:
    aU= 'SQUARE_METERS'

# -------------------------Preprocessing--------------------

#Raster to polygon using inR
try:
    print 'vectorizing raster'
    arcpy.AddMessage('vectorizing raster')
    arcpy.conversion.RasterToPolygon(inR, 'poly.shp', 'NO_SIMPLIFY', 'VALUE')
    poly = 'poly.shp'
    print 'done!'
    
    #create fishnet using fnS and inR(for extent) 
    print 'generating fishnet'
    arcpy.AddMessage('generating fishnet')
    arcpy.management.CreateFishnet('fishnet.shp',origin_coord, axY_coord, fnS, fnS, '', '', oc_coord, 'NO_LABELS', '', 'POLYGON')
    fNet = 'fishnet.shp'
    print fNet
    print 'done!'
    
    #split polygons poly using fNet
    print 'splitting polygons!'
    arcpy.AddMessage('splitting polygons')
    #arcpy.SplitPolygons(poly,'ENVELOPE',fNet,'#','FEATURE','split_poly.shp')
    arcpy.Intersect_analysis([poly,fNet], 'split_poly.shp','','','INPUT')
    spPoly = 'split_poly.shp'
    print 'done!'
    
    #Multipart polygons To Singlepart polygons
    print 'unmultiparting polygons'
    arcpy.AddMessage('unmultiparting polygons')
    
    arcpy.MultipartToSinglepart_management(spPoly, 'sPrt_spPoly.shp')
    spPoly = 'sPrt_spPoly.shp'
    print 'Filtering too small polygons'
    arcpy.AddMessage('Filtering small polygons')
    #add geometry attribute (area) for filtering too small polygons
    print 'Adding geometry field'
    arcpy.AddGeometryAttributes_management(spPoly, 'AREA','',aU)

    #get rid of too small polygons in spPoly using pT 
    #convert the feature class into a layer using Make Feature Layer
    print 'Making feature layer'
    arcpy.MakeFeatureLayer_management(spPoly, 'split_poly_l')
    
    # Select all polys which are bigger than threshold
    condition = """ "POLY_AREA">"""+str(pT)
    print 'where clausure:'+condition
    print 'Selecting by attribute'
    arcpy.SelectLayerByAttribute_management('split_poly_l', 'NEW_SELECTION', condition)
    # Write the selected features to a new featureclass
    print 'saving selected features'    
    arcpy.CopyFeatures_management('split_poly_l', 'fSpPoly.shp')
    fSpPoly = 'fSpPoly.shp'
    print 'Done filtering, new file '+ fSpPoly+' created'
   
    #create centroids
    print 'generating centroids'
    arcpy.AddMessage('generating centroids')
    arcpy.FeatureToPoint_management(fSpPoly,'point_fr_poly.shp', 'CENTROID')
    pnts = 'point_fr_poly.shp'

    #Create Thiessen polygons
    print 'generating Thiessen polygons'
    arcpy.AddMessage('generating Thiessen polygons')
    arcpy.CreateThiessenPolygons_analysis(pnts, 'thissen.shp', 'ONLY_FID')
    tPoly = 'thissen.shp'
    
    #clip Thiessen polygons with raster extent
    #Create a polygon footprint of  a raster dataset
    arcpy.MinimumBoundingGeometry_management (poly, 'bound_poly.shp', 'ENVELOPE', 'ALL')
    bp = 'bound_poly.shp'
    arcpy.Clip_analysis (tPoly, bp, 'tPolyclip.shp')
    tPoly='tPolyclip.shp'
    
 
   
# --------------------------Processing----------------------

    #zonal statistics (Pixels per area count)
    print 'counting pixesl'
    arcpy.AddMessage('Calculating nubmer of pixels per square unit')
    pixCntR = arcpy.sa.ZonalStatistics(tPoly,'FID', inR, 'SUM', 'DATA') 

    #zonal geometry (Generation of raster with area of each Voronoi polygon)
    print 'counting area'
    arR = arcpy.sa.ZonalGeometry(tPoly, 'FID', 'AREA', rCllSz) 

    #map algebra (pixels per square unit calculation using Raster calculator) 
    print 'counting ratio'
    pxPsqMtrR = pixCntR/arR

    #Extract pixels per square unit values to points for further Heat map generation
    print 'extracting values to points'
    arcpy.sa.ExtractValuesToPoints (pnts, pxPsqMtrR, 'extr_val_to_p.shp', 'NONE', 'VALUE_ONLY')
    pnts = 'extr_val_to_p.shp'  


    #Interpolate obtained points to a surface
    print 'interpolating a heat map'
    arcpy.AddMessage('Interpolating a heat map')
    outR = arcpy.sa.Idw(pnts, 'RASTERVALU', rCllSz,'1') #+'interType'
    print 'saving raster as '+outRst
    outR.save(outRst)

    #clear memory
    print 'Doing some cleaning'
    del inR
    del outR
    del outRst
    del rCllSz
    del poly
    del fNet 
    del spPoly 
    del fSpPoly
    del pnts
    del tPoly
    del pixCntR
    del arR
    del pxPsqMtrR
    del bp

    #clear disc
    arcpy.Delete_management('extr_val_to_p.shp')
    arcpy.Delete_management('thissen.shp')
    arcpy.Delete_management('point_fr_poly.shp')
    arcpy.Delete_management('poly.shp')
    arcpy.Delete_management('fishnet.shp')
    arcpy.Delete_management('bound_poly.shp')
    arcpy.Delete_management('tPolyclip.shp')
    arcpy.Delete_management('fSpPoly.shp')
    arcpy.Delete_management('split_poly.shp')
    arcpy.Delete_management('sPrt_spPoly.shp')
    print 'comleted!'
    arcpy.AddMessage('Ta-daaaaa!')
except:
   print arcpy.GetMessages()
