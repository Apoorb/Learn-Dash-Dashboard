import os
import json
import pandas as pd
import geopandas as gpd
import re
import plotly.express as px
import plotly.io as pio
import folium

pio.renderers.default = "browser"

if __name__ == "__main__":
    # Read Crash Statistics.
    path_to_raw="data/raw"
    path_to_processed= os.path.normpath("./data/processed")
    path_to_crash_df = os.path.normpath("./data/raw/Crash_Statistics.xlsx")
    crash_x1 = pd.ExcelFile(path_to_crash_df)
    crash_sheets = crash_x1.sheet_names
    print(f"Following sheets need to be read: f{crash_sheets}")
    keep_name_re = re.compile(r"(?P<sheet_nm>\w*)(?:(\(?\d*)\)?)")
    # Sheet names as keys and clean sentence case county names as values.
    sheet_county_map = {
        crash_sheet: re.match(keep_name_re, crash_sheet).group("sheet_nm")
        for crash_sheet in crash_sheets
    }
    # Iterate over different counties and read the crash data by counties.
    df_list = []
    for sheet_nm, county_nm in sheet_county_map.items():
        df = pd.read_excel(crash_x1, sheet_nm, skiprows=2)
        rename_map = {col: int(col) for col in df.columns if col != "Unnamed: 0"}
        rename_map["Unnamed: 0"] = "crash_cat"
        df = df.rename(columns=rename_map).assign(
            crash_cat=lambda df: df.crash_cat.str.strip()
        )
        df.loc[:, "county"] = county_nm
        df_list.append(df)
    # Get one crash data for all counties.
    crash_df = pd.concat(df_list)
    # There is a sheet for STATEWIDE crashes. We only need the county data for
    # now.
    crash_df_county = crash_df.query("county.str.upper()!='STATEWIDE'")

    # Read County shapefile. Will use this for spatial plot.
    path_to_boundaries = r"./data/boundaries/Pennsylvania_County_Boundaries.gdb"
    county_shp = gpd.read_file(path_to_boundaries)
    county_shp = county_shp.to_crs(epsg=4326)
    # Get long data; stack yearly crash columns.
    crash_df_county_long = (
        crash_df_county
        .melt(
            id_vars=["county", "crash_cat"],
            var_name="crash_year",
            value_name="crash_freq")
        .assign(county=lambda df: df.county.str.strip())
    )
    # Add geometry to the long crash data by year and counties.
    county_shp_crash_df = (
        county_shp
        .assign(COUNTY_NAME=lambda df: df.COUNTY_NAME.str.strip().str.upper())
        .merge(
            crash_df_county_long.assign(
                county_temp=lambda df: df.county.str.upper()),
            left_on="COUNTY_NAME",
            right_on="county_temp",
            how="left",
        )
        .drop(columns="county_temp")
    )
    # Check that the merge retained values from both left and right data.
    assert county_shp_crash_df.county.isna().sum() == 0, (
        "Check county spell-" "ing in the two " "dataset."
    )
    # Clean county names.
    crash_df_county_long_v1 = crash_df_county_long.assign(
        COUNTY_NAME=lambda df: df.county.str.strip().str.upper()
    )
    # Get the data in geojson format.
    county_shp_geojson = json.loads(county_shp.to_json())
    # Test plotly choropleth map.
    fig = px.choropleth_mapbox(
        crash_df_county_long_v1.loc[
            lambda df: (df.crash_year == 2019)
                       & (df.crash_cat == "Total Crashes")
        ],
        geojson=county_shp_geojson,
        locations="COUNTY_NAME",
        featureidkey="properties.COUNTY_NAME",
        color="crash_freq",
        color_continuous_scale="Viridis",
        mapbox_style="carto-positron",
        zoom=3,
        center={"lat": 40, "lon": -77},
        labels={"crash_freq": "Crash Frequency"},
    )
    fig.update_geos(fitbounds="locations", visible=True)
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig.show()



    ##############################  X  #########################################
    # Create a folium map to re-create above figure.
    test = crash_df_county_long_v1.loc[
        lambda df: (df.crash_year == 2019) & (df.crash_cat == "Total Crashes")
    ]
    m = folium.Map(location=[40.3, -77.05], zoom_start=11, tiles="cartodbpositron")
    folium.Choropleth(
        geo_data=county_shp_geojson,
        data=test,
        columns=["COUNTY_NAME", "crash_freq"],
        key_on="properties.COUNTY_NAME",
        fill_color="YlGn",
        fill_opacity=0.6,
        line_opacity=0.2,
    ).add_to(m)
    path_folium_map=os.path.join(path_to_processed, "folium_penndot_crash.html")
    m.save(path_folium_map)
