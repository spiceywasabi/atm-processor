module("luci.controller.atm.atm_config", package.seeall)  --notice that atm_config is the name of the file atm_config.lua
 function index()
     entry({"admin", "atm_config"}, firstchild(), "ATM", 60).dependent=false  --this adds the top level tab and defaults to the first sub-tab (tab_from_cbi), also it is set to position 30
     entry({"admin", "atm_config", "atm_setup"}, cbi("atm/atm_setup"), "ATM Setup", 1)
--     entry({"admin", "atm_config", "tab_from_cbi"}, cbi("atm/cbi_tab"), "CBI Tab", 2)
--     entry({"admin", "atm_config", "tab_from_view"}, template("atm/view_tab"), "View Tab", 3)
end

