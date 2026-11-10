# SPHEREx Sky Diary — Data Adapter Layer

**Module:** Module 1  
**Status:** Implemented (MockSource fully functional; IrsaFitsSource stubbed)  
**Maintainer / Point of Contact:** Data Adapter Team (Harnoor)  

---

## 1. Architectural Overview

The SPHEREx data adapter layer provides an isolated abstraction between raw mission/synthetic data files and the downstream scientific pipeline (`detection`, `matching`, `spectra`). 

```
                       ┌──────────────────────┐
                       │  config/settings.yaml │
                       │ (data_source: mock)  │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │    Adapter Factory   │
                       │     (get_source)     │
                       └──────────┬───────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       ┌─────────────────────┐         ┌─────────────────────┐
       │     MockSource      │         │   IrsaFitsSource    │
       │ (Synthetic Planes,  │         │  (Real IPAC/IRSA    │
       │  Ground Truth JSON) │         │   FITS Deliveries)  │
       └──────────┬──────────┘         └──────────┬──────────┘
                  │                               │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                         EpochSource Interface
                       ┌──────────────────────┐
                       │ - list_epochs()      │
                       │ - load_epoch()       │
                       │ - get_ground_truth() │
                       └──────────┬───────────┘
                                  │ Returns
                                  ▼
                       ┌──────────────────────┐
                       │      EpochImage      │
                       │  - pixels (2D)       │
                       │  - variance (2D)     │
                       │  - mask (2D bitmask) │
                       │  - wcs (Astropy WCS) │
                       │  - wavelength_map    │
                       └──────────────────────┘
```

---

## 2. Core Domain Types & Interface

All definitions reside in [`data/adapter/base.py`](file:///data/adapter/base.py).

### Data Classes
* **`Region`**: Target celestial coordinates and radius:
  * `name: str`
  * `ra_center: float` (0.0 to 360.0 degrees)
  * `dec_center: float` (-90.0 to 90.0 degrees)
  * `radius_deg: float` (> 0.0)
* **`EpochInfo`**: High-level observation pass descriptor:
  * `epoch_id: str` (e.g., `"mock_epoch_01"`)
  * `date: datetime` (UTC timestamp)
  * `files: list[str | Path]` (originating FITS files or URIs)
  * `band_count: int` (number of spectral channels, default 102)
  * `metadata: dict` (includes `is_synthetic: bool`)
* **`EpochImage`**: In-memory calibrated 2D observation plane for a single epoch:
  * `pixels: np.ndarray` (2D float64 array of image flux)
  * `variance: np.ndarray` (2D float64 variance plane matching pixels)
  * `mask: np.ndarray` (2D int32 bitmask: bit 1 = bad/dead pixel, bit 2 = cosmic ray)
  * `wcs: astropy.wcs.WCS` (astrometric world coordinate system)
  * `wavelength_map: np.ndarray` (2D float64 map of effective wavelengths in microns, 0.75 – 5.0 µm)
  * `epoch_id: str`
  * `date: datetime`
  * `metadata: dict`

### Abstract Interface: `EpochSource`
```python
class EpochSource(ABC):
    @abstractmethod
    def list_epochs(self, region: Region) -> list[EpochInfo]:
        """List available observation epochs sorted ascending by date."""
        pass

    @abstractmethod
    def load_epoch(self, epoch_id: str, region: Region, fov_deg: float = 0.2) -> EpochImage:
        """Load calibrated epoch plane for given region and field-of-view."""
        pass

    @abstractmethod
    def get_ground_truth(self) -> dict | None:
        """Retrieve synthetic ground truth dictionary (None for real flight data)."""
        pass
```

---

## 3. How to Add a New Source

To implement a new backend (e.g. simulation cubes, private mirror):

1. **Subclass `EpochSource`**:
   ```python
   from data.adapter.base import EpochSource, Region, EpochInfo, EpochImage

   class CustomSource(EpochSource):
       def list_epochs(self, region: Region) -> list[EpochInfo]:
           ...
       def load_epoch(self, epoch_id: str, region: Region, fov_deg: float = 0.2) -> EpochImage:
           ...
       def get_ground_truth(self) -> dict | None:
           return None
   ```
2. **Register in Factory** ([`data/adapter/factory.py`](file:///data/adapter/factory.py)):
   Add your identifier to `get_source`:
   ```python
   elif data_source == "custom":
       return CustomSource(...)
   ```
3. **Configure**: Update `config/settings.yaml`:
   ```yaml
   data_source: custom
   ```

---

## 4. Harnoor's Real SPHEREx / IRSA Verification Checklist

> [!IMPORTANT]
> The real SPHEREx file hierarchy and FITS HDU conventions are unreleased or unverified. **Never guess or hardcode extension names.** Mark all assumptions with `TODO(VERIFY)`.

When official SPHEREx IRSA deliveries are inspected, tick off each item below and implement the corresponding parsing in [`data/adapter/irsa_source.py`](file:///data/adapter/irsa_source.py):

- [ ] **1. File Organization and Extension Layout:**
  - Are public products distributed as single-exposure FITS, multi-extension spectral cubes (MEF), or spatial tile coadds?
  - What are the file naming schemes and standard extensions (`.fits`, `.fits.gz`)?
- [ ] **2. WCS Storage & Distortion Representation:**
  - Is the celestial WCS located exclusively in the Primary HDU or duplicated/overridden per image extension?
  - Does SPHEREx use standard TAN projection with CD matrix/CDELT, or SIP polynomial distortion coefficients?
- [ ] **3. Per-Pixel Wavelength Mapping:**
  - How is wavelength encoded across the linear variable filter (LVF)?
  - Is there an explicit `WAVELENGTH` HDU/table, or is dispersion expressed via header polynomials ($a_0 + a_1 x + a_2 y$)?
- [ ] **4. Data Quality / Mask Extension & Bitmask Meanings:**
  - What is the exact extension name (e.g., `DQ`, `MASK`, `FLAGS`)?
  - What are the integer bit meanings (e.g. Bit 0: bad pixel, Bit 1: cosmic ray, Bit 2: saturation, Bit 3: edge)?
- [ ] **5. Uncertainty / Variance Extension:**
  - What is the HDU name (e.g., `UNCERT`, `VAR`, `ERR`, `SIGMA`)?
  - Are values 1-sigma standard deviation ($\sigma$) or variance ($\sigma^2$)?
  - What physical units are used (e.g., $\text{MJy/sr}$, $\text{e}^-/\text{s}$, $\mu\text{Jy}$)?
- [ ] **6. Effective PSF & Header Centering Convention:**
  - Is an empirical or modeled PSF attached as an extension?
  - **PSF Header Caveat:** Verify pixel grid centering (Fortran 1-based indexing vs Python 0-based indexing) to prevent systematic 0.5-pixel astrometric offsets.
- [ ] **7. Epoch Grouping & Timestamp Criteria:**
  - How should individual visits/orbits be grouped into an "epoch"?
  - Which FITS header keys define canonical timestamps (`DATE-OBS`, `MJD-OBS`, `TIME-OBS`)?

---

## 5. Metadata Catalog

The metadata catalog provides a fast tabular index for archive searches and pipeline staging:

* **File:** `data/output/metadata_catalog.csv`
* **Schema:**
  * `epoch_id` (string)
  * `date` (ISO 8601 UTC)
  * `band_or_channel` (string, e.g., `"bands_1-102"`)
  * `ra_min`, `ra_max`, `dec_min`, `dec_max` (float celestial bounding box)
  * `file_path` (URI or local path)
  * `is_synthetic` (boolean)
* **API:**
  * `build_catalog(source, region) -> Path`
  * `read_catalog(path) -> pd.DataFrame`
