from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from normalizers import LABELS, REGISTRY, get_normalizer
from normalizers.base import NormalizationCandidate
from utils.anomalies import scan_anomalies
from utils.detect import scan_dataframe
from utils.text_extract import (
    SUPPORTED_EXTENSIONS as TEXT_DOC_EXTS,
    extract_document,
    rebuild_document,
)
from utils.text_scan import (
    apply_replacements as apply_text_replacements,
    group_by_type,
    scan_text_document,
)
