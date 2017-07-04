#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for converting FFMPEG files into standardized MP4s'''


import os
import sys
import subprocess
from xml.etree import ElementTree

import logging
logger = logging.getLogger(__name__)


def probe(filename):
  '''Calls ffprobe and returns parsed output

  The executable ``ffprobe`` should be installed alongside
  :py:attr:`sys.executable`.


  Parameters:

    filename (str): Full path leading to the multimedia file to be parsed


  Returns:

    xml.etree.ElementTree: With all information pre-parsed by the stock XML
    parser. A typical stream has the following structure:

    .. code-block:: xml

     <ffprobe>
       <streams>
         <stream index="0" codec_name="h264" codec_long_name="H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10" profile="Constrained Baseline" codec_type="video" codec_time_base="1/60" codec_tag_string="avc1" codec_tag="0x31637661" width="560" height="320" coded_width="560" coded_height="320" has_b_frames="0" sample_aspect_ratio="0:1" display_aspect_ratio="0:1" pix_fmt="yuv420p" level="30" color_range="tv" color_space="bt709" color_transfer="bt709" color_primaries="bt709" chroma_location="left" refs="1" is_avc="true" nal_length_size="4" r_frame_rate="30/1" avg_frame_rate="30/1" time_base="1/90000" start_pts="0" start_time="0.000000" duration_ts="498000" duration="5.533333" bit_rate="465641" bits_per_raw_sample="8" nb_frames="166">
           <disposition default="1" dub="0" original="0" comment="0" lyrics="0" karaoke="0" forced="0" hearing_impaired="0" visual_impaired="0" clean_effects="0" attached_pic="0" timed_thumbnails="0"/>
           <tag key="creation_time" value="2010-03-20T21:29:11.000000Z"/>
           <tag key="language" value="und"/>
           <tag key="encoder" value="JVT/AVC Coding"/>
         </stream>
         <stream>...</stream>
       </streams>
       <format filename="/Users/andre/Projects/qnap/librarian/librarian/data/movie.mp4" nb_streams="2" nb_programs="0" format_name="mov,mp4,m4a,3gp,3g2,mj2" format_long_name="QuickTime / MOV" start_time="0.000000" duration="5.568000" size="383631" bit_rate="551193" probe_score="100">
         <tag key="major_brand" value="mp42"/>
         <tag key="minor_version" value="0"/>
         <tag key="compatible_brands" value="mp42isomavc1"/>
         <tag key="creation_time" value="2010-03-20T21:29:11.000000Z"/>
         <tag key="encoder" value="HandBrake 0.9.4 2009112300"/>
       </format>
     </ffprobe>


  Raises:

    IOError: In case ``ffprobe`` is not available on your path

  '''

  ffprobe = os.path.join(os.path.dirname(sys.executable), 'ffprobe')

  # checks ffprobe is there...
  if not os.path.exists(ffprobe):
    raise IOError('Cannot find ffprobe exectuable at `%s\' - did you ' \
        'install it?' % ffprobe)

  cmd = [
      ffprobe,
      '-v', 'quiet',
      '-print_format', 'xml',
      '-show_format',
      '-show_streams',
      filename,
      ]

  try:
    data = subprocess.check_output(cmd)
  except Exception as e:
    logger.error("Error running command `%s'" % ' '.join(cmd))
    raise

  return ElementTree.fromstring(data)
