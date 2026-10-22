"""Builds training/train_plant_id_model.ipynb:  python training/build_plant_notebook.py training/train_plant_id_model.ipynb"""
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")})


def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n")})


md("""
# PhytoSense AR – plant identification + leaf-condition model

Trains **one fast model with two outputs**:

* **Species** – 55 plants common in Indore / central India (money plant, rose, banyan, peepal, neem, tulsi, gulmohar …),
  the 13 crops of the disease model, and a *not a plant* class.
* **Leaf condition** – healthy, leaf spot / blight, powdery mildew, rust, sooty mould, mosaic / yellowing, pest infestation.
  These general symptom groups work on *any* plant, including the ones no disease dataset covers.

**Data (all free, downloaded by this notebook):** research-grade field photos from **iNaturalist** (CC-licensed,
Indian observations first), PlantVillage + PlantDoc for the crops, and Imagenette for *not a plant*.

**Run:** `Runtime → Change runtime type → T4 GPU`, then `Runtime → Run all` (≈ 60–80 min: ~20 min download, ~45 min training).
At the end it downloads `phytosense_plant_model.zip` → unzip into `PhytoSense-AR/backend/model/`.

To add or remove a plant, edit `LOCAL_PLANTS` below **and** add a matching entry to `backend/data/plants.json`.
""")

code("""
!nvidia-smi --query-gpu=name,memory.total --format=csv
!pip -q install timm onnx onnxruntime
import torch
assert torch.cuda.is_available(), "Select a GPU runtime: Runtime -> Change runtime type -> T4 GPU"
""")

md("## 1. Classes")
code("""
# id -> iNaturalist taxon (exact scientific name). Order does not matter.
LOCAL_PLANTS = {
    # trees
    "banyan": "Ficus benghalensis", "peepal": "Ficus religiosa", "neem": "Azadirachta indica",
    "mango": "Mangifera indica", "ashoka": "Monoon longifolium", "gulmohar": "Delonix regia",
    "amaltas": "Cassia fistula", "jamun": "Syzygium cumini", "guava": "Psidium guajava",
    "papaya": "Carica papaya", "banana": "Musa", "coconut": "Cocos nucifera",
    "tamarind": "Tamarindus indica", "arjun": "Terminalia arjuna", "eucalyptus": "Eucalyptus",
    "teak": "Tectona grandis", "moringa": "Moringa oleifera", "citrus": "Citrus",
    "pomegranate": "Punica granatum", "bamboo": "Bambusoideae", "custard_apple": "Annona squamosa",
    "bael": "Aegle marmelos", "saptaparni": "Alstonia scholaris", "ber": "Ziziphus mauritiana",
    # flowering shrubs and garden plants
    "rose": "Rosa", "hibiscus": "Hibiscus rosa-sinensis", "bougainvillea": "Bougainvillea",
    "marigold": "Tagetes", "mogra": "Jasminum sambac", "parijat": "Nyctanthes arbor-tristis",
    "kaner": "Nerium oleander", "yellow_kaner": "Cascabela thevetia", "chandni": "Tabernaemontana divaricata",
    "ixora": "Ixora", "sadabahar": "Catharanthus roseus", "lantana": "Lantana camara",
    "aak": "Calotropis", "adenium": "Adenium obesum",
    # herbs
    "tulsi": "Ocimum tenuiflorum", "curry_leaf": "Bergera koenigii", "mint": "Mentha",
    "aloe": "Aloe vera", "henna": "Lawsonia inermis",
    # house plants
    "money_plant": "Epipremnum aureum", "snake_plant": "Sansevieria trifasciata",
    "areca_palm": "Chrysalidocarpus lutescens", "croton": "Codiaeum variegatum",
    "spider_plant": "Chlorophytum comosum", "jade": "Crassula ovata", "rubber_plant": "Ficus elastica",
    "coleus": "Coleus scutellarioides",
    # vegetables / field crops of the region and a common weed
    "brinjal": "Solanum melongena", "okra": "Abelmoschus esculentus", "wheat": "Triticum aestivum",
    "parthenium": "Parthenium hysterophorus",
}
# Crops of the disease model: PlantVillage folder prefix -> (species id, iNaturalist taxon)
CROPS = {
    "Apple": ("apple", "Malus domestica"), "Blueberry": ("blueberry", "Vaccinium corymbosum"),
    "Cherry_(including_sour)": ("cherry", "Prunus avium"), "Corn_(maize)": ("corn", "Zea mays"),
    "Grape": ("grape", "Vitis vinifera"), "Orange": ("citrus", None), "Peach": ("peach", "Prunus persica"),
    "Pepper,_bell": ("capsicum", "Capsicum annuum"), "Potato": ("potato", "Solanum tuberosum"),
    "Raspberry": ("raspberry", "Rubus idaeus"), "Soybean": ("soybean", "Glycine max"),
    "Squash": ("squash", "Cucurbita"), "Strawberry": ("strawberry", "Fragaria ananassa"),
    "Tomato": ("tomato", "Solanum lycopersicum"),
}
TAXA = dict(LOCAL_PLANTS)
TAXA.update({sid: tax for sid, tax in CROPS.values() if tax})
SPECIES = sorted(TAXA) + ["not_plant"]
SP2I = {s: i for i, s in enumerate(SPECIES)}

CONDITIONS = ["healthy", "leaf_spot_blight", "powdery_mildew", "rust", "sooty_mould", "mosaic_yellowing", "pest_infestation"]
C2I = {c: i for i, c in enumerate(CONDITIONS)}
# iNaturalist taxa whose observations show the symptom (on many different host plants)
SYMPTOM_TAXA = {
    "leaf_spot_blight": ["Diplocarpon rosae", "Phyllosticta", "Cercospora", "Colletotrichum",
                         "Venturia inaequalis", "Rhytisma", "Peronosporaceae"],
    "powdery_mildew": ["Erysiphaceae"],
    "rust": ["Pucciniales"],
    "sooty_mould": ["Capnodiaceae", "Meliolaceae"],
    "mosaic_yellowing": ["Potyviridae", "Begomovirus"],
    "pest_infestation": ["Pseudococcidae", "Aphididae", "Aleyrodidae", "Coccoidea", "Tetranychidae",
                         "Phyllocnistis citrella"],
}
# PlantVillage label -> condition group
def pv_condition(label):
    d = label.split("___")[1].lower()
    if "healthy" in d: return "healthy"
    if "powdery" in d: return "powdery_mildew"
    if "rust" in d: return "rust"
    if "mosaic" in d or "curl" in d or "greening" in d: return "mosaic_yellowing"
    if "mite" in d: return "pest_infestation"
    return "leaf_spot_blight"

PER_SPECIES = 320          # iNaturalist photos per plant
PER_SYMPTOM = 900          # iNaturalist photos per condition group
PV_PER_LABEL = 70          # PlantVillage photos per disease label (crops also get PlantDoc + iNaturalist)
print(len(SPECIES), "species classes,", len(CONDITIONS), "condition classes")
""")

md("## 2. Download iNaturalist photos (≈ 20 min)")
code("""
import io, json, random, time, csv, re, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

random.seed(42)
API = "https://api.inaturalist.org/v1"
LIC = "cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nc-sa"
S = requests.Session(); S.headers["User-Agent"] = "PhytoSense-AR college project (plant id training)"
IMG = Path("/content/img"); IMG.mkdir(exist_ok=True)

def api(path, **params):
    for attempt in range(6):
        r = S.get(f"{API}/{path}", params=params, timeout=60)
        if r.status_code == 200:
            time.sleep(1.0)                       # iNaturalist asks for <= 1 request/second
            return r.json()
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()

def resolve(name):
    for t in api("taxa", q=name, per_page=30)["results"]:
        if t["name"].replace("\\u00d7 ", "").replace("× ", "").lower() == name.lower():
            return t["id"]
    raise ValueError(f"iNaturalist taxon not found: {name}")

def observations(taxon_id, n):
    \"\"\"Up to n observations with an openly licensed photo: India first, then worldwide; research grade first.\"\"\"
    out, seen = [], set()
    for extra in ({"place_id": 6681, "quality_grade": "research"}, {"quality_grade": "research"},
                  {"quality_grade": "needs_id,casual"}):
        below = None
        while len(out) < n:
            p = dict(taxon_id=taxon_id, photos="true", photo_license=LIC, per_page=200,
                     order_by="id", order="desc", **extra)
            if below: p["id_below"] = below
            res = api("observations", **p)["results"]
            if not res: break
            for o in res:
                ph = o["photos"][0]
                if o["id"] in seen or ph.get("license_code") is None: continue
                seen.add(o["id"])
                out.append({"obs": o["id"], "url": ph["url"].replace("/square.", "/medium."),
                            "license": ph["license_code"], "attribution": ph.get("attribution", "")})
            below = res[-1]["id"]
        if len(out) >= n: break
    return out[:n]

inat = {}      # (kind, class) -> list of records
for sid, name in sorted(TAXA.items()):
    inat[("species", sid)] = observations(resolve(name), PER_SPECIES)
    print(f"{sid:15s} {name:28s} {len(inat[('species', sid)])}")
for cond, names in SYMPTOM_TAXA.items():
    recs = []
    for name in names:
        recs += observations(resolve(name), PER_SYMPTOM // len(names) + 60)
    random.shuffle(recs)
    inat[("condition", cond)] = recs[:PER_SYMPTOM]
    print(f"{cond:20s} {len(inat[('condition', cond)])}")
""")

code("""
def fetch(rec):
    dst = IMG / f"inat_{rec['obs']}.jpg"
    if not dst.exists():
        for attempt in range(3):
            try:
                r = S.get(rec["url"], timeout=30); r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
                im.thumbnail((320, 320), Image.BILINEAR); im.save(dst, quality=90)
                break
            except Exception:
                time.sleep(2)
        else:
            return None
    return dst

all_recs = [r for recs in inat.values() for r in recs]
with ThreadPoolExecutor(12) as ex:
    paths = list(ex.map(fetch, all_recs))
for r, p in zip(all_recs, paths):
    r["path"] = p
print(sum(p is not None for p in paths), "of", len(all_recs), "photos downloaded")

with open("/content/inat_attribution.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["kind", "class", "observation_url", "license", "attribution"])
    for (kind, cls), recs in inat.items():
        for r in recs:
            if r["path"]: w.writerow([kind, cls, f"https://www.inaturalist.org/observations/{r['obs']}", r["license"], r["attribution"]])
""")

md("## 3. PlantVillage, PlantDoc and *not a plant* images")
code("""
%cd /content
!git clone -q --depth 1 https://github.com/pratikkayal/PlantDoc-Dataset.git
!git clone -q --depth 1 --filter=blob:none --sparse https://github.com/spMohanty/PlantVillage-Dataset.git
!cd PlantVillage-Dataset && git sparse-checkout set raw/color
!wget -q https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-320.tgz && tar -xzf imagenette2-320.tgz
!ls PlantDoc-Dataset/train | wc -l; ls PlantVillage-Dataset/raw/color | wc -l; ls imagenette2-320/train
""")

code("""
PD = Path("/content/PlantDoc-Dataset"); PV = Path("/content/PlantVillage-Dataset/raw/color")
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PLANTDOC_TO_PV = {
    "apple scab leaf": "Apple___Apple_scab", "apple leaf": "Apple___healthy", "apple rust leaf": "Apple___Cedar_apple_rust",
    "bell_pepper leaf spot": "Pepper,_bell___Bacterial_spot", "bell_pepper leaf": "Pepper,_bell___healthy",
    "blueberry leaf": "Blueberry___healthy", "cherry leaf": "Cherry_(including_sour)___healthy",
    "corn gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot", "corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "corn rust leaf": "Corn_(maize)___Common_rust_", "peach leaf": "Peach___healthy", "potato leaf": "Potato___healthy",
    "potato leaf early blight": "Potato___Early_blight", "potato leaf late blight": "Potato___Late_blight",
    "raspberry leaf": "Raspberry___healthy", "soyabean leaf": "Soybean___healthy", "squash powdery mildew leaf": "Squash___Powdery_mildew",
    "strawberry leaf": "Strawberry___healthy", "tomato early blight leaf": "Tomato___Early_blight",
    "tomato septoria leaf spot": "Tomato___Septoria_leaf_spot", "tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "tomato leaf late blight": "Tomato___Late_blight", "tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "tomato leaf": "Tomato___healthy",
    "tomato mold leaf": "Tomato___Leaf_Mold", "tomato two spotted spider mites leaf": "Tomato___Spider_mites Two-spotted_spider_mite",
    "grape leaf black rot": "Grape___Black_rot", "grape leaf": "Grape___healthy",
}
norm = lambda s: re.sub(r"\\s+", " ", s.strip().lower())
pv_species = lambda label: SP2I[CROPS[label.split("___")[0]][0]]

def shrink(src, dst):
    if not dst.exists():
        try:
            im = Image.open(src).convert("RGB"); im.thumbnail((320, 320), Image.BILINEAR); im.save(dst, quality=90)
        except Exception:
            return None
    return dst

# item = (path, species index or -1, condition index or -1, condition weight)
jobs = {"train": [], "val": [], "test": []}
def add(split, src, sp, cond, w=1.0, prefix=""):
    jobs[split].append((src, IMG / f"{prefix}{abs(hash(str(src)))}.jpg", sp, cond, w))

for label_dir in sorted(PV.iterdir()):
    files = sorted(p for p in label_dir.iterdir() if p.suffix.lower() in IMG_EXT); random.shuffle(files)
    sp, cond = pv_species(label_dir.name), C2I[pv_condition(label_dir.name)]
    for p in files[:10]: add("test", p, sp, cond, prefix="pv_")
    for p in files[10:20]: add("val", p, sp, cond, prefix="pv_")
    for p in files[20:20 + PV_PER_LABEL]: add("train", p, sp, cond, prefix="pv_")

for split_dir, splits in (("train", None), ("test", "test")):
    for d in sorted((PD / split_dir).iterdir()):
        if not d.is_dir(): continue
        label = PLANTDOC_TO_PV[norm(d.name)]
        sp, cond = pv_species(label), C2I[pv_condition(label)]
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in IMG_EXT: continue
            split = splits or ("val" if random.random() < 0.1 else "train")
            add(split, p, sp, cond, prefix="pd_")

notplant = sorted(Path("/content/imagenette2-320/train").rglob("*.JPEG")); random.shuffle(notplant)
for i, p in enumerate(notplant[:1300]):
    add("test" if i < 150 else "val" if i < 300 else "train", p, SP2I["not_plant"], -1, prefix="in_")

with ThreadPoolExecutor(8) as ex:
    done = {s: list(ex.map(lambda j: shrink(j[0], j[1]), js)) for s, js in jobs.items()}
items = {s: [(dst, sp, c, w) for (src, _, sp, c, w), dst in zip(js, done[s]) if dst] for s, js in jobs.items()}

# iNaturalist: split by observation, 70 / 15 / 15
for (kind, cls), recs in inat.items():
    recs = [r for r in recs if r["path"]]
    random.shuffle(recs)
    n = len(recs); a, b = int(0.7 * n), int(0.85 * n)
    for split, part in (("train", recs[:a]), ("val", recs[a:b]), ("test", recs[b:])):
        for r in part:
            if kind == "species":     # most iNaturalist plant photos show healthy plants -> weak "healthy" label
                items[split].append((r["path"], SP2I[cls], C2I["healthy"], 0.3))
            else:                     # symptom photos: condition known, host plant not used
                items[split].append((r["path"], -1, C2I[cls], 1.0))
for s in items: random.shuffle(items[s])
print({s: len(v) for s, v in items.items()})
""")

md("## 4. Model: ConvNeXt-Tiny (ImageNet-22k pre-trained) with two heads")
code("""
import numpy as np, timm, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms as T

MEAN, STD, SIZE = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225], 224

def app_preprocess(im):
    # Same as backend/app/plant_id.py: squash to 224x224 (bilinear), scale 0-1, ImageNet mean/std, CHW.
    x = np.asarray(im.resize((SIZE, SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    x = (x - np.array(MEAN, np.float32)) / np.array(STD, np.float32)
    return torch.from_numpy(x.transpose(2, 0, 1))

train_aug = T.Compose([
    T.RandomResizedCrop(SIZE, scale=(0.3, 1.0), ratio=(0.75, 1.33)),
    T.RandomHorizontalFlip(), T.RandomVerticalFlip(p=0.2), T.RandomRotation(20),
    T.ColorJitter(0.35, 0.35, 0.3, 0.02),
    T.RandomApply([T.GaussianBlur(5, sigma=(0.1, 1.8))], p=0.25),
])

class Images(Dataset):
    def __init__(self, items, train): self.items, self.train = items, train
    def __len__(self): return len(self.items)
    def __getitem__(self, i):
        p, sp, c, w = self.items[i]
        im = Image.open(p).convert("RGB")
        if self.train: im = train_aug(im)
        return app_preprocess(im), sp, c, torch.tensor(w, dtype=torch.float32)

BATCH = 64
loader = lambda its, train: DataLoader(Images(its, train), batch_size=BATCH, shuffle=train, num_workers=2,
                                       pin_memory=True, drop_last=train, persistent_workers=train)

class PlantNet(nn.Module):
    def __init__(self, n_sp, n_cond):
        super().__init__()
        self.backbone = timm.create_model("convnext_tiny.fb_in22k_ft_in1k", pretrained=True, num_classes=0, drop_path_rate=0.1)
        d = self.backbone.num_features
        self.species, self.condition = nn.Linear(d, n_sp), nn.Linear(d, n_cond)
    def forward(self, x):
        f = self.backbone(x)
        return self.species(f), self.condition(f)

model = PlantNet(len(SPECIES), len(CONDITIONS)).cuda()
""")

md("## 5. Train (≈ 45 min)")
code("""
import copy
from transformers import get_cosine_schedule_with_warmup

EPOCHS = 12
train_dl = loader(items["train"], True)
opt = torch.optim.AdamW([{"params": model.backbone.parameters(), "lr": 1e-4},
                         {"params": list(model.species.parameters()) + list(model.condition.parameters()), "lr": 1e-3}],
                        weight_decay=0.05)
steps = EPOCHS * len(train_dl)
sched = get_cosine_schedule_with_warmup(opt, int(0.05 * steps), steps)
scaler = torch.amp.GradScaler("cuda")
ce = nn.CrossEntropyLoss(label_smoothing=0.1, ignore_index=-1, reduction="none")

@torch.no_grad()
def evaluate(model, its):
    model.eval(); sp_ok = sp_n = sp_top5 = c_ok = c_n = 0
    preds = []
    for x, sp, c, _ in loader(its, False):
        with torch.autocast("cuda", dtype=torch.float16):
            ls, lc = model(x.cuda())
        ls, lc = ls.float().cpu(), lc.float().cpu()
        m = sp >= 0
        sp_ok += (ls.argmax(1)[m] == sp[m]).sum().item(); sp_n += m.sum().item()
        sp_top5 += (ls.topk(5, 1).indices[m] == sp[m].unsqueeze(1)).any(1).sum().item()
        mc = c >= 0
        c_ok += (lc.argmax(1)[mc] == c[mc]).sum().item(); c_n += mc.sum().item()
        preds += list(zip(sp.tolist(), ls.argmax(1).tolist(), c.tolist(), lc.argmax(1).tolist()))
    return {"species_top1": sp_ok / max(sp_n, 1), "species_top5": sp_top5 / max(sp_n, 1),
            "condition_acc": c_ok / max(c_n, 1)}, preds

best, best_state, history = -1, None, []
for epoch in range(1, EPOCHS + 1):
    model.train(); t0 = time.time(); total = 0
    for x, sp, c, w in train_dl:
        x, sp, c, w = x.cuda(non_blocking=True), sp.cuda(), c.cuda(), w.cuda()
        with torch.autocast("cuda", dtype=torch.float16):
            ls, lc = model(x)
        ls, lc = ls.float(), lc.float()
        msp, mc = sp >= 0, c >= 0
        loss_sp = ce(ls, sp).sum() / msp.sum().clamp(min=1)
        loss_c = (ce(lc, c) * w).sum() / (w * mc).sum().clamp(min=1)
        loss = loss_sp + loss_c
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward(); scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update(); sched.step()
        total += loss.item()
    val, _ = evaluate(model, items["val"])
    score = val["species_top1"] + val["condition_acc"]
    history.append({"epoch": epoch, "loss": total / len(train_dl), **val})
    print(f"epoch {epoch}: loss {total/len(train_dl):.3f} | val species {val['species_top1']:.1%} "
          f"(top5 {val['species_top5']:.1%}) | condition {val['condition_acc']:.1%} | {time.time()-t0:.0f}s")
    if score > best:
        best, best_state = score, copy.deepcopy(model.state_dict())
model.load_state_dict(best_state)
""")

md("## 6. Test results (for the report)")
code("""
from collections import defaultdict
test, preds = evaluate(model, items["test"])
print("TEST:", {k: f"{v:.1%}" for k, v in test.items()})

per_sp = defaultdict(lambda: [0, 0]); per_c = defaultdict(lambda: [0, 0]); confusions = defaultdict(int)
for sp, psp, c, pc in preds:
    if sp >= 0:
        per_sp[SPECIES[sp]][0] += sp == psp; per_sp[SPECIES[sp]][1] += 1
        if sp != psp: confusions[(SPECIES[sp], SPECIES[psp])] += 1
    if c >= 0:
        per_c[CONDITIONS[c]][0] += c == pc; per_c[CONDITIONS[c]][1] += 1
print("\\nSpecies (lowest 15):")
for k, (ok, n) in sorted(per_sp.items(), key=lambda kv: kv[1][0] / kv[1][1])[:15]:
    print(f"  {k:15s} {ok:3d}/{n:<3d} {ok/n:6.1%}")
print("\\nConditions:")
for k, (ok, n) in per_c.items():
    print(f"  {k:18s} {ok:4d}/{n:<4d} {ok/n:6.1%}")
print("\\nMost common confusions:", sorted(confusions.items(), key=lambda kv: -kv[1])[:10])

# Field photos only: PlantDoc test (crop recognition) and iNaturalist local plants
pd_test = [it for it in items["test"] if Path(it[0]).name.startswith("pd_")]
local_test = [it for it in items["test"] if Path(it[0]).name.startswith("inat_") and it[1] >= 0]
pd_res, _ = evaluate(model, pd_test); local_res, _ = evaluate(model, local_test)
print(f"\\nPlantDoc field photos: crop identified {pd_res['species_top1']:.1%}, condition {pd_res['condition_acc']:.1%}")
print(f"iNaturalist plants: species top-1 {local_res['species_top1']:.1%}, top-5 {local_res['species_top5']:.1%}")
""")

md("## 7. Export int8 ONNX for the app and check it")
code("""
import onnxruntime as ort
from onnxruntime.quantization import QuantType, quantize_dynamic

OUT = Path("/content/export"); OUT.mkdir(exist_ok=True)
cpu = model.float().cpu().eval()
torch.onnx.export(cpu, (torch.zeros(2, 3, SIZE, SIZE),), str(OUT / "fp32.onnx"), input_names=["pixel_values"],
                  output_names=["species_logits", "condition_logits"], opset_version=17, dynamo=False,
                  dynamic_axes={"pixel_values": {0: "batch"}, "species_logits": {0: "batch"}, "condition_logits": {0: "batch"}})
# int8 only for MatMul/Gemm: as small as full quantisation but ~2x faster on CPU (ConvInteger is slow).
quantize_dynamic(str(OUT / "fp32.onnx"), str(OUT / "plant_model.onnx"), weight_type=QuantType.QInt8,
                 op_types_to_quantize=["MatMul", "Gemm"])
for f in OUT.glob("fp32.onnx*"): f.unlink()

sess = ort.InferenceSession(str(OUT / "plant_model.onnx"), providers=["CPUExecutionProvider"])
ok_sp = n_sp = ok_c = n_c = 0
for p, sp, c, _ in random.sample(items["test"], min(1500, len(items["test"]))):
    ls, lc = sess.run(None, {"pixel_values": app_preprocess(Image.open(p).convert("RGB"))[None].numpy()})
    if sp >= 0: ok_sp += int(ls[0].argmax()) == sp; n_sp += 1
    if c >= 0: ok_c += int(lc[0].argmax()) == c; n_c += 1
x2 = np.zeros((2, 3, SIZE, SIZE), np.float32); sess.run(None, {"pixel_values": x2}); t0 = time.time()
for _ in range(10): sess.run(None, {"pixel_values": x2})
cpu_ms = (time.time() - t0) / 10 * 1000
int8 = {"species_top1": ok_sp / n_sp, "condition_acc": ok_c / n_c}
print(f"int8 ONNX: species {int8['species_top1']:.1%}, condition {int8['condition_acc']:.1%}, "
      f"{(OUT/'plant_model.onnx').stat().st_size/1e6:.0f} MB, {cpu_ms:.0f} ms per 2-image batch on Colab CPU")

(OUT / "plant_labels.json").write_text(json.dumps({
    "arch": "convnext_tiny.fb_in22k_ft_in1k", "input_size": SIZE, "mean": MEAN, "std": STD,
    "species": SPECIES, "conditions": CONDITIONS}, indent=1), encoding="utf-8")
(OUT / "plant_metrics.json").write_text(json.dumps({
    "test": test, "test_int8_onnx": int8, "plantdoc_field": pd_res, "inaturalist_plants": local_res,
    "per_species": {k: ok / n for k, (ok, n) in per_sp.items()}, "per_condition": {k: ok / n for k, (ok, n) in per_c.items()},
    "split_sizes": {s: len(v) for s, v in items.items()}, "history": history, "cpu_ms_batch2": cpu_ms}, indent=1), encoding="utf-8")
!cp /content/inat_attribution.csv /content/export/
!cd /content/export && zip -q /content/phytosense_plant_model.zip plant_model.onnx plant_labels.json plant_metrics.json inat_attribution.csv
from google.colab import files
files.download("/content/phytosense_plant_model.zip")
""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                                    "kernelspec": {"name": "python3", "display_name": "Python 3"}},
      "nbformat": 4, "nbformat_minor": 0}
for c in nb["cells"]:
    c["source"] = c["source"].splitlines(keepends=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("wrote", OUT)
