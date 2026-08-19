// @ts-nocheck
/**
 * CountryMap.config.ts — Sub-national choropleth map for any country.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 *
 * Renders states/provinces/regions WITHIN a single country using publicly
 * available GeoJSON boundaries. Works for India, UK, Germany, Brazil, etc.
 *
 * geoJsonUrl: URL to a public GeoJSON file with admin-1 boundaries (states/provinces).
 *   Common sources:
 *     India:    https://raw.githubusercontent.com/geohacker/india/master/state/india_telengana.geojson
 *     UK:       https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/gb/lad.json
 *     Germany:  https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json
 *     France:   https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions.geojson
 *     Brazil:   https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson
 *     Canada:   https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/canada.geojson
 *     Australia:https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/australia.geojson
 *     Japan:    https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson
 *     China:    https://raw.githubusercontent.com/nicholasgasior/geojson-maps/master/china.json
 *     Mexico:   https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/mexico.geojson
 *     Italy:    https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson
 *     Spain:    https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/spain-communities.geojson
 *     South Africa: https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/south-africa.geojson
 *     Nigeria:  https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/nigeria.geojson
 *     Indonesia:https://raw.githubusercontent.com/nicholasgasior/geojson-maps/master/indonesia.json
 *
 * regionNameProp: The property name in the GeoJSON features that contains the
 *   region/state name. Common values: 'NAME_1', 'name', 'NAME', 'admin', 'state', 'region'
 */
export const config = {
  tableName: '{{TABLE_NAME}}',             // SQLite table name — data auto-fetched from /api/data/{tableName}
  dataExport: null as any[] | null,        // null = use tableName API

  // Country name (for display title)
  countryName: '{{COUNTRY_NAME}}',

  // URL to public GeoJSON with sub-national boundaries (states/provinces/regions)
  geoJsonUrl: '{{GEO_JSON_URL}}',

  // Property in GeoJSON features containing the region/state name
  regionNameProp: '{{REGION_NAME_PROP}}',

  // Field in YOUR data that contains the region/state name (must match GeoJSON names)
  regionField: '{{REGION_FIELD}}',

  // Numeric field that drives colour intensity
  valueField: '{{VALUE_FIELD}}',

  // Label field for tooltips (often same as regionField)
  labelField: '{{LABEL_FIELD}}',

  title: '{{CHART_TITLE}}',

  // Colour ramp: 'blue' | 'green' | 'orange' | 'purple' | 'red'
  colorScheme: '{{COLOR_SCHEME}}' as 'blue' | 'green' | 'orange' | 'purple' | 'red',

  // Value display format (d3.format string, e.g. ',.0f', '$,.1f', '.1%')
  valueFormat: '{{VALUE_FORMAT}}',

  // Dropdown filter field — set to null if not needed
  filterField: {{FILTER_FIELD}},
} as const
