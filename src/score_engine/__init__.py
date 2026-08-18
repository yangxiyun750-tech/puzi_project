"""Score Engine — core score processing package.

Contains:
- score_ir: Canonical intermediate representation for musical scores
- musicxml: MusicXML import/export
- validation: Round-trip validation and instrument identity resolution
- measure_locator: Measure-to-PDF coordinate mapping
"""

from score_engine.score_ir import *
from score_engine.musicxml import MusicXMLImporter, MusicXMLExporter
from score_engine.validation import RoundtripValidator, InstrumentIdentityResolver
from score_engine.measure_locator import MeasureLocator, EvidenceCropper
