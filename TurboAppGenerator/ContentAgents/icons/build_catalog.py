"""
Curates a shared, per-service icon catalog for AWS/GCP/Azure from each
provider's own official icon asset package -- used by both ppt_creator
(python-pptx insert_picture, needs PNG) and video_creator (Remotion <Img>
via staticFile, canonical SVG). NOT part of either agent's runtime path --
a maintenance script, re-run only when refreshing/expanding the catalog.

Official source packages (URLs are versioned/change over time -- re-check
the provider's own icon page before re-running against a fresh download):
    AWS:   https://aws.amazon.com/architecture/icons/
           -> "Icon-package_<date>....zip" (ships matching SVG+PNG)
    GCP:   https://cloud.google.com/icons -> "google-cloud-legacy-icons.zip"
           (NOT "core-products-icons.zip", which is only ~19 flagship
           products -- "legacy" is, despite the name, the real per-service
           catalog with 200+ services, ships matching SVG+PNG)
    Azure: https://learn.microsoft.com/en-us/azure/architecture/icons/
           -> "Azure_Public_Service_Icons_V*.zip" (SVG ONLY -- no official
           PNG at all, unlike AWS/GCP -- see azure/README note below)
    general: not a cloud provider -- `npm install @tabler/icons` in a
           scratch dir (MIT licensed, see LICENSE.md), then point --src at
           its package root (node_modules/@tabler/icons). SVG only, same
           rasterize-to-PNG handling as Azure.

Usage (run once per provider, after downloading+extracting its zip):
    python build_catalog.py --provider aws --src <path to extracted AWS zip>
    python build_catalog.py --provider gcp --src <path to extracted "legacy" zip>
    python build_catalog.py --provider azure --src <path to extracted Azure zip>
    python build_catalog.py --provider general --src <path to @tabler/icons package root>

Azure has no official PNG, so that provider's run also rasterizes each
curated SVG to PNG via `@resvg/resvg-js` (Rust-based, no native Windows
build deps -- svglib/reportlab were tried first and choke on real Azure
icons using <clipPath>; cairosvg needs system Cairo/GTK libs that are a
known pain on Windows). This needs a throwaway `npm install @resvg/resvg-js`
in a scratch dir -- not a permanent dependency of this repo, only used at
curation time; the generated PNGs are what actually get committed/used.

Each run overwrites only that provider's section of catalog.json and its
own svg/png subfolders -- other providers are untouched.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ICONS_DIR = Path(__file__).resolve().parent
CATALOG_PATH = ICONS_DIR / "catalog.json"

# name -> exact filename stem (no extension) in the provider's OWN package,
# hand-picked directly from a real listing of each package's contents (never
# guessed from memory) -- the ~50-90 services that actually come up in an
# architecture-overview brief, not an exhaustive dump of every service the
# package contains (AWS alone ships 300+, most far too niche to be worth
# cataloging: Thinkbox render-farm plugins, quantum computing, satellite
# ground stations, etc).

# AWS: stem is <category>/<stem>, since the package nests services under a
# category folder before the size folder (see _curate_aws below).
AWS_SERVICES = {
    "ec2": "Compute/Amazon-EC2", "lambda": "Compute/AWS-Lambda",
    "ecs": "Containers/Amazon-Elastic-Container-Service", "eks": "Containers/Amazon-Elastic-Kubernetes-Service",
    "ecr": "Containers/Amazon-Elastic-Container-Registry", "fargate": "Containers/AWS-Fargate",
    "batch": "Compute/AWS-Batch", "lightsail": "Compute/Amazon-Lightsail",
    "elastic-beanstalk": "Compute/AWS-Elastic-Beanstalk", "ec2-auto-scaling": "Compute/Amazon-EC2-Auto-Scaling",
    "outposts": "Compute/AWS-Outposts-family",
    "s3": "Storage/Amazon-Simple-Storage-Service", "s3-glacier": "Storage/Amazon-Simple-Storage-Service-Glacier",
    "ebs": "Storage/Amazon-Elastic-Block-Store", "efs": "Storage/Amazon-EFS", "fsx": "Storage/Amazon-FSx",
    "backup": "Storage/AWS-Backup", "storage-gateway": "Storage/AWS-Storage-Gateway", "snowball": "Storage/AWS-Snowball",
    "rds": "Databases/Amazon-RDS", "dynamodb": "Databases/Amazon-DynamoDB", "aurora": "Databases/Amazon-Aurora",
    "elasticache": "Databases/Amazon-ElastiCache", "documentdb": "Databases/Amazon-DocumentDB",
    "neptune": "Databases/Amazon-Neptune", "database-migration-service": "Databases/AWS-Database-Migration-Service",
    "timestream": "Databases/Amazon-Timestream",
    "vpc": "Networking-Content-Delivery/Amazon-Virtual-Private-Cloud",
    "cloudfront": "Networking-Content-Delivery/Amazon-CloudFront", "route53": "Networking-Content-Delivery/Amazon-Route-53",
    "elastic-load-balancing": "Networking-Content-Delivery/Elastic-Load-Balancing",
    "api-gateway": "Networking-Content-Delivery/Amazon-API-Gateway",
    "direct-connect": "Networking-Content-Delivery/AWS-Direct-Connect",
    "transit-gateway": "Networking-Content-Delivery/AWS-Transit-Gateway",
    "site-to-site-vpn": "Networking-Content-Delivery/AWS-Site-to-Site-VPN",
    "global-accelerator": "Networking-Content-Delivery/AWS-Global-Accelerator",
    "privatelink": "Networking-Content-Delivery/AWS-PrivateLink",
    "iam": "Security-Identity/AWS-Identity-and-Access-Management", "kms": "Security-Identity/AWS-Key-Management-Service",
    "cognito": "Security-Identity/Amazon-Cognito", "secrets-manager": "Security-Identity/AWS-Secrets-Manager",
    "shield": "Security-Identity/AWS-Shield", "waf": "Security-Identity/AWS-WAF",
    "guardduty": "Security-Identity/Amazon-GuardDuty", "security-hub": "Security-Identity/AWS-Security-Hub",
    "certificate-manager": "Security-Identity/AWS-Certificate-Manager", "inspector": "Security-Identity/Amazon-Inspector",
    "macie": "Security-Identity/Amazon-Macie",
    "sqs": "Application-Integration/Amazon-Simple-Queue-Service",
    "sns": "Application-Integration/Amazon-Simple-Notification-Service",
    "eventbridge": "Application-Integration/Amazon-EventBridge", "step-functions": "Application-Integration/AWS-Step-Functions",
    "mq": "Application-Integration/Amazon-MQ", "appsync": "Application-Integration/AWS-AppSync",
    "athena": "Analytics/Amazon-Athena", "kinesis": "Analytics/Amazon-Kinesis", "glue": "Analytics/AWS-Glue",
    "emr": "Analytics/Amazon-EMR", "opensearch": "Analytics/Amazon-OpenSearch-Service", "redshift": "Analytics/Amazon-Redshift",
    "cloudwatch": "Management-Tools/Amazon-CloudWatch", "cloudformation": "Management-Tools/AWS-CloudFormation",
    "systems-manager": "Management-Tools/AWS-Systems-Manager", "cloudtrail": "Management-Tools/AWS-CloudTrail",
    "config": "Management-Tools/AWS-Config", "organizations": "Management-Tools/AWS-Organizations",
    "trusted-advisor": "Management-Tools/AWS-Trusted-Advisor", "auto-scaling": "Management-Tools/AWS-Auto-Scaling",
    "managed-grafana": "Management-Tools/Amazon-Managed-Grafana",
    "codepipeline": "Developer-Tools/AWS-CodePipeline", "codebuild": "Developer-Tools/AWS-CodeBuild",
    "codecommit": "Developer-Tools/AWS-CodeCommit", "codedeploy": "Developer-Tools/AWS-CodeDeploy",
    "cloud9": "Developer-Tools/AWS-Cloud9", "x-ray": "Developer-Tools/AWS-X-Ray",
    "sagemaker": "Artificial-Intelligence/Amazon-SageMaker-AI", "bedrock": "Artificial-Intelligence/Amazon-Bedrock",
    "rekognition": "Artificial-Intelligence/Amazon-Rekognition", "comprehend": "Artificial-Intelligence/Amazon-Comprehend",
    "textract": "Artificial-Intelligence/Amazon-Textract", "polly": "Artificial-Intelligence/Amazon-Polly",
    "transcribe": "Artificial-Intelligence/Amazon-Transcribe", "lex": "Artificial-Intelligence/Amazon-Lex",
    "translate": "Artificial-Intelligence/Amazon-Translate", "forecast": "Artificial-Intelligence/Amazon-Forecast",
    "kendra": "Artificial-Intelligence/Amazon-Kendra", "q": "Artificial-Intelligence/Amazon-Q",
    "datasync": "Migration-Modernization/AWS-DataSync",
    "application-migration-service": "Migration-Modernization/AWS-Application-Migration-Service",
    "transfer-family": "Migration-Modernization/AWS-Transfer-Family",
    "amplify": "Front-End-Web-Mobile/AWS-Amplify", "location-service": "Front-End-Web-Mobile/Amazon-Location-Service",
}

# GCP: "legacy" package is a flat <slug>/<slug>.{svg,png} per service --
# values here are just the slug (folder name), hand-picked from a real
# listing of the package's ~216 folders.
GCP_SERVICES = {
    "compute-engine": "compute_engine", "app-engine": "app_engine", "cloud-functions": "cloud_functions",
    "cloud-run": "cloud_run", "gke": "google_kubernetes_engine", "batch": "batch",
    "cloud-storage": "cloud_storage", "persistent-disk": "persistent_disk", "filestore": "filestore",
    "cloud-sql": "cloud_sql", "cloud-spanner": "cloud_spanner", "bigtable": "bigtable",
    "firestore": "firestore", "memorystore": "memorystore",
    # AlloyDB/Cloud Identity/Resource Manager have no folder at all in this
    # "legacy" package (AlloyDB is newer than this package's freeze; the
    # other two just aren't in it) -- verified against the real listing,
    # not omitted by oversight. AlloyDB is in the separate "Unique Icons"
    # (core-products) pack instead, a different naming scheme, out of
    # scope for this pass.
    "vpc": "virtual_private_cloud", "cloud-load-balancing": "cloud_load_balancing", "cloud-cdn": "cloud_cdn",
    "cloud-dns": "cloud_dns", "cloud-nat": "cloud_nat", "cloud-vpn": "cloud_vpn",
    "cloud-interconnect": "cloud_interconnect", "cloud-armor": "cloud_armor",
    "iam": "identity_and_access_management", "cloud-kms": "key_management_service", "secret-manager": "secret_manager",
    "security-command-center": "security_command_center",
    "pub-sub": "pubsub", "eventarc": "eventarc", "workflows": "workflows",
    "cloud-tasks": "cloud_tasks", "cloud-scheduler": "cloud_scheduler",
    "bigquery": "bigquery", "dataflow": "dataflow", "dataproc": "dataproc", "composer": "cloud_composer",
    "looker": "looker", "data-catalog": "data_catalog", "dataplex": "dataplex",
    "artifact-registry": "artifact_registry", "cloud-build": "cloud_build", "cloud-deploy": "cloud_deploy",
    "container-registry": "container_registry",
    "vertex-ai": "vertexai", "automl": "automl", "vision-ai": "cloud_vision_api",
    "natural-language-ai": "cloud_natural_language_api", "speech-to-text": "speech-to-text",
    "text-to-speech": "text-to-speech", "translation-ai": "cloud_translation_api",
    "cloud-monitoring": "cloud_monitoring", "cloud-logging": "cloud_logging",
    "cloud-trace": "trace", "error-reporting": "error_reporting",
    "storage-transfer": "transfer", "anthos": "anthos",
    "api-gateway": "cloud_api_gateway", "apigee": "apigee_api_platform",
    "cloud-billing": "billing",
}

# Azure: category folder -> exact filename (with its numeric prefix), hand-
# picked from a real listing of the package's ~714 files across ~25
# category folders.
AZURE_SERVICES = {
    "virtual-machine": "compute/10021-icon-service-Virtual-Machine",
    "kubernetes-service": "compute/10023-icon-service-Kubernetes-Services",
    "app-service": "app services/10035-icon-service-App-Services",
    "container-instances": "containers/10104-icon-service-Container-Instances",
    "container-registry": "containers/10105-icon-service-Container-Registries",
    "azure-functions": "compute/10029-icon-service-Function-Apps",
    "batch": "compute/10031-icon-service-Batch-Accounts",
    "virtual-machine-scale-sets": "compute/10034-icon-service-VM-Scale-Sets",
    "disk-storage": "compute/10032-icon-service-Disks",
    "blob-storage": "storage/10086-icon-service-Storage-Accounts",
    "files": "storage/10093-icon-service-Storage-Sync-Services",
    "sql-database": "databases/10130-icon-service-SQL-Database",
    "sql-managed-instance": "databases/10136-icon-service-SQL-Managed-Instance",
    "cosmos-db": "databases/10121-icon-service-Azure-Cosmos-DB",
    "database-for-mysql": "databases/10122-icon-service-Azure-Database-MySQL-Server",
    "database-for-postgresql": "databases/02827-icon-service-Azure-Database-PostgreSQL-Server-Group",
    "azure-sql": "databases/02390-icon-service-Azure-SQL",
    "virtual-network": "networking/10061-icon-service-Virtual-Networks",
    "load-balancer": "networking/10062-icon-service-Load-Balancers",
    "application-gateway": "networking/10076-icon-service-Application-Gateways",
    "vpn-gateway": "networking/10063-icon-service-Virtual-Network-Gateways",
    "front-door": "networking/10073-icon-service-Front-Door-and-CDN-Profiles",
    "traffic-manager": "networking/10065-icon-service-Traffic-Manager-Profiles",
    "cdn-profiles": "networking/00056-icon-service-CDN-Profiles",
    "express-route": "networking/10079-icon-service-ExpressRoute-Circuits",
    "azure-firewall": "networking/10084-icon-service-Firewalls",
    # No flagship "Azure Active Directory"/"Microsoft Entra ID" root icon
    # exists in this V24 package at all (only Entra sub-feature icons like
    # Connect/PIM/ID-Protection) -- a real gap in the source material,
    # verified by searching the full listing, not an oversight here.
    "key-vault": "security/10245-icon-service-Key-Vaults",
    "microsoft-defender-for-cloud": "security/10241-icon-service-Microsoft-Defender-for-Cloud",
    "azure-sentinel": "security/10248-icon-service-Azure-Sentinel",
    "service-bus": "integration/10836-icon-service-Azure-Service-Bus",
    "event-grid": "integration/10206-icon-service-Event-Grid-Topics",
    "logic-apps": "integration/02631-icon-service-Logic-Apps",
    "api-management": "integration/10042-icon-service-API-Management-Services",
    "event-hubs": "analytics/00039-icon-service-Event-Hubs",
    "synapse-analytics": "databases/00606-icon-service-Azure-Synapse-Analytics",
    "data-factory": "databases/10126-icon-service-Data-Factories",
    "databricks": "analytics/10787-icon-service-Azure-Databricks",
    "hdinsight": "analytics/10142-icon-service-HD-Insight-Clusters",
    "stream-analytics": "analytics/00042-icon-service-Stream-Analytics-Jobs",
    "azure-monitor": "monitor/00001-icon-service-Monitor",
    "log-analytics": "management + governance/00009-icon-service-Log-Analytics-Workspaces",
    "azure-devops": "devops/10261-icon-service-Azure-DevOps",
    "azure-machine-learning": "ai + machine learning/10166-icon-service-Machine-Learning",
    "cognitive-services": "ai + machine learning/10162-icon-service-Cognitive-Services",
    "openai-service": "ai + machine learning/03438-icon-service-Azure-OpenAI",
    "bot-services": "ai + machine learning/10165-icon-service-Bot-Services",
}


def _clean_stem(name: str) -> str:
    return name.lower().replace(" ", "-")


def _curate_aws(src: Path) -> dict[str, str]:
    """AWS package layout: Architecture-Service-Icons_<date>/Arch_<Category>/64/Arch_<Service>_64.{svg,png}"""
    root = next(src.glob("Architecture-Service-Icons_*"), None) or src
    svg_dir, png_dir = ICONS_DIR / "aws" / "svg", ICONS_DIR / "aws" / "png"
    result = {}
    for name, rel in AWS_SERVICES.items():
        category, stem = rel.split("/", 1)
        base = root / f"Arch_{category}" / "64" / f"Arch_{stem}_64"
        svg_src, png_src = base.with_suffix(".svg"), base.with_suffix(".png")
        if not svg_src.exists() or not png_src.exists():
            print(f"  [aws] MISSING: {name} -> {base.name} (looked in {base.parent})", file=sys.stderr)
            continue
        clean = _clean_stem(name)
        shutil.copy(svg_src, svg_dir / f"{clean}.svg")
        shutil.copy(png_src, png_dir / f"{clean}.png")
        result[clean] = clean
    return result


def _curate_gcp(src: Path) -> dict[str, str]:
    """GCP "legacy" package layout: <slug>/<slug>.{svg,png}"""
    svg_dir, png_dir = ICONS_DIR / "gcp" / "svg", ICONS_DIR / "gcp" / "png"
    result = {}
    for name, slug in GCP_SERVICES.items():
        base = src / slug / slug
        svg_src, png_src = base.with_suffix(".svg"), base.with_suffix(".png")
        if not svg_src.exists() or not png_src.exists():
            print(f"  [gcp] MISSING: {name} -> {slug} (looked in {src / slug})", file=sys.stderr)
            continue
        clean = _clean_stem(name)
        shutil.copy(svg_src, svg_dir / f"{clean}.svg")
        shutil.copy(png_src, png_dir / f"{clean}.png")
        result[clean] = clean
    return result


def _curate_azure(src: Path) -> dict[str, str]:
    """Azure package layout: Icons/<category>/<NNNNN>-icon-service-<Name>.svg -- SVG only,
    no official PNG (see module docstring), so PNGs are rasterized here via resvg-js."""
    root = next(src.glob("Azure_Public_Service_Icons"), None) or src
    icons_root = root / "Icons"
    svg_dir, png_dir = ICONS_DIR / "azure" / "svg", ICONS_DIR / "azure" / "png"
    matched: dict[str, Path] = {}
    for name, rel in AZURE_SERVICES.items():
        category, stem = rel.split("/", 1)
        svg_src = icons_root / category / f"{stem}.svg"
        if not svg_src.exists():
            print(f"  [azure] MISSING: {name} -> {stem} (looked in {icons_root / category})", file=sys.stderr)
            continue
        clean = _clean_stem(name)
        shutil.copy(svg_src, svg_dir / f"{clean}.svg")
        matched[clean] = svg_dir / f"{clean}.svg"

    if matched:
        _rasterize_svgs_to_pngs(matched, png_dir)
    return {k: k for k in matched}


# general/: hand-picked non-cloud business/automotive concept icons, sourced
# from Tabler Icons (`@tabler/icons` npm package, MIT licensed) rather than
# any provider's own package -- see LICENSE.md. Values are the outline-style
# source filename (no .svg) under node_modules/@tabler/icons/icons/outline/.
GENERAL_SERVICES = {
    "dealership": "building-store",
    "car": "car",
    "owner": "user",
    "supplier": "truck-delivery",
    "oem": "building-factory",
}


def _curate_general(src: Path) -> dict[str, str]:
    """`src` is the installed @tabler/icons package root (the dir containing
    icons/outline/*.svg), e.g. `npm install @tabler/icons` in a scratch dir
    then pass its node_modules/@tabler/icons path here. SVG only like Azure,
    so also rasterized to PNG. Tabler's SVGs use stroke="currentColor" with
    no surrounding CSS to resolve it, so that's replaced with a fixed dark
    hex before rasterizing (matches ppt_creator's own dark-line-art icons)."""
    icons_root = src / "icons" / "outline"
    svg_dir, png_dir = ICONS_DIR / "general" / "svg", ICONS_DIR / "general" / "png"
    matched: dict[str, Path] = {}
    for name, stem in GENERAL_SERVICES.items():
        svg_src = icons_root / f"{stem}.svg"
        if not svg_src.exists():
            print(f"  [general] MISSING: {name} -> {stem} (looked in {icons_root})", file=sys.stderr)
            continue
        clean = _clean_stem(name)
        svg_text = svg_src.read_text(encoding="utf-8").replace('stroke="currentColor"', 'stroke="#0B0B0B"')
        (svg_dir / f"{clean}.svg").write_text(svg_text, encoding="utf-8")
        matched[clean] = svg_dir / f"{clean}.svg"

    if matched:
        _rasterize_svgs_to_pngs(matched, png_dir)
    return {k: k for k in matched}


def _rasterize_svgs_to_pngs(matched: dict[str, Path], png_dir: Path) -> None:
    """One-time SVG->PNG conversion for a provider with no official PNG
    (Azure; general/'s Tabler source). Uses a throwaway
    `npm install @resvg/resvg-js` in a scratch dir -- not a permanent
    dependency of this repo."""
    import tempfile

    scratch = Path(tempfile.mkdtemp(prefix="azure_svg2png_"))
    subprocess.run(["npm", "install", "@resvg/resvg-js", "--silent"], cwd=scratch, shell=True, check=True)
    script = scratch / "convert.mjs"
    script.write_text(
        "import { Resvg } from '@resvg/resvg-js';\n"
        "import { readFileSync, writeFileSync } from 'fs';\n"
        "const [svgPath, pngPath] = process.argv.slice(2);\n"
        "const svg = readFileSync(svgPath);\n"
        "const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: 256 }, background: 'rgba(255,255,255,0)' });\n"
        "writeFileSync(pngPath, resvg.render().asPng());\n",
        encoding="utf-8",
    )
    for clean, svg_path in matched.items():
        png_path = png_dir / f"{clean}.png"
        subprocess.run(["node", str(script), str(svg_path), str(png_path)], cwd=scratch, check=True)
    shutil.rmtree(scratch, ignore_errors=True)


_CURATORS = {"aws": _curate_aws, "gcp": _curate_gcp, "azure": _curate_azure, "general": _curate_general}
_SERVICE_LISTS = {"aws": AWS_SERVICES, "gcp": GCP_SERVICES, "azure": AZURE_SERVICES, "general": GENERAL_SERVICES}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=list(_CURATORS))
    ap.add_argument("--src", required=True, type=Path, help="Path to the extracted official icon package")
    args = ap.parse_args()

    for sub in ("svg", "png"):
        (ICONS_DIR / args.provider / sub).mkdir(parents=True, exist_ok=True)

    matched = _CURATORS[args.provider](args.src)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8")) if CATALOG_PATH.exists() else {}
    catalog[args.provider] = matched
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{args.provider}: curated {len(matched)}/{len(_SERVICE_LISTS[args.provider])} icons -> catalog.json")


if __name__ == "__main__":
    main()
