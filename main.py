"""

FastAPI application for the DHS Checker API.

This application exposes a single endpoint ``/check_ids/`` that accepts a
CSV file containing a column named ``ID Number``.  The endpoint
processes the CSV, extracts each RSA ID number, invokes the scraping
logic contained in ``dhs_checker.py`` to fetch the debt review status
and debt counsellor trading name from the NCR Debt Help System and
returns the results as JSON.

The application uses Playwright under the hood to automate a headless
browser session.  Playwright is installed at runtime using a
post-install script defined in ``railway.json``.  Ensure that the
environment variables ``DHS_USERNAME`` and ``DHS_PASSWORD`` are set
when running this application so that the scraper can authenticate.
"""

from __future__ import annotations

import csv
import io
from typing import List, Dict, Optional
from pydantic import BaseModel


from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

import dhs_checker


app = FastAPI(title="DHS Checker API", version="1.0.0")


@app.post("/check_ids/", response_class=JSONResponse)
async def check_ids(file: UploadFile = File(...)) -> List[Dict[str, Optional[str]]]:
    """Accept a CSV file and return debt review information for each ID.

    The uploaded CSV must contain a header named ``ID Number``.  Each
    row in this column should contain a valid South African ID number
    (13-digit string).  The endpoint reads the CSV in memory, extracts
    the values from the ``ID Number`` column and passes them to the
    ``dhs_checker.check_ids`` coroutine.  The resulting list of
    dictionaries is returned to the caller as JSON.

    :param file: The uploaded CSV file containing ID numbers.
    :returns: A list of dictionaries with keys ``id_number``,
              ``status`` and ``debt_counsellor``.
    :raises HTTPException: If the CSV is malformed or missing the
                           required column.
    """
    # Read the uploaded file into memory.  FastAPI's UploadFile
    # provides an async interface but reading small files synchronously
    # into a bytes buffer is acceptable here.  We decode using
    # universal newline support to handle different OS line endings.
    try:
        contents = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}")

    # Use csv.DictReader to parse the CSV contents.  We assume UTF-8
    # encoding.  If the file uses a different encoding you may need to
    # adjust the decode call accordingly.
    try:
        csv_text = contents.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Unable to decode CSV file as UTF-8: {exc}")

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV file appears to be empty or missing a header row.")

    # Normalize field names by stripping whitespace and case to allow
    # variations such as "id number" or "ID number".  We create a
    # mapping from normalized names to original names for extraction.
    normalized_fields = {name.strip().lower(): name for name in reader.fieldnames}
    id_column_name = normalized_fields.get("id number")
    if not id_column_name:
        raise HTTPException(status_code=400, detail="CSV file must contain a column named 'ID Number'.")

    # Extract ID numbers from each row.  Skip rows where the ID value
    # is missing or empty.
    id_numbers: List[str] = []
    for row in reader:
        value = row.get(id_column_name)
        if value:
            id_numbers.append(value.strip())

    if not id_numbers:
        raise HTTPException(status_code=400, detail="No ID numbers found in the CSV file.")

    # Delegate to the scraper.  If the scraper raises an exception it
    # will propagate and return a 500 error to the client.
    results = await dhs_checker.check_ids(id_numbers)
    return results


class IDRequest(BaseModel):
    id_number: str

@app.post("/check_id/", response_class=JSONResponse)
async def check_id(id_request: IDRequest):
    """
    Accept a single ID number and return debt review information for that ID.
    """
    try:
        results = await dhs_checker.check_ids([id_request.id_number])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not results:
        raise HTTPException(status_code=404, detail="ID not found")
    return results[0]


@app.get("/check_id_get/", response_class=JSONResponse)
async def check_id_get(id_number: str):
    """
    Accept a single ID number via a query parameter and return debt review information for that ID as JSON.
    """
    try:
        results = await dhs_checker.check_ids([id_number])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not results:
        raise HTTPException(status_code=404, detail="ID not found")
    return results[0]
