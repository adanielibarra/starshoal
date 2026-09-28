"""Make the plugin importable as the package 'starshoal' from its parent folder."""
import os
import sys

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(PLUGIN))
