"""
FamiLator - NES/Famicom ROM Automated Text Extraction, Translation & Reinjection

A Python-based tool for extracting, translating, and reinserting text from NES and Famicom ROMs
using modern AI and traditional ROM hacking techniques.
"""

__version__ = "0.1.0"
__author__ = "Matt-Retrogamer"

from .extractor import TextExtractor
from .reinjector import TextReinjector
from .encoding import EncodingTable
from .detector import TextDetector
from .validator import ROMValidator

__all__ = [
    "TextExtractor",
    "TextReinjector", 
    "EncodingTable",
    "TextDetector",
    "ROMValidator"
]
