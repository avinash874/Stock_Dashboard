import { useStockDashboard } from "./hooks/useStockDashboard";
import { FooterSection } from "./sections/FooterSection";
import { HeaderSection } from "./sections/HeaderSection";
import { MainSection } from "./sections/MainSection";
import { SidebarSection } from "./sections/SidebarSection";

export default function App() {
  const d = useStockDashboard();

  return (
    <div className="min-h-screen flex flex-col">
      <HeaderSection
        rangeDays={d.rangeDays}
        onRangeChange={d.onRangeChange}
        showMA={d.showMA}
        setShowMA={d.setShowMA}
        showPred={d.showPred}
        setShowPred={d.setShowPred}
      />

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        <SidebarSection
          search={d.search}
          setSearch={d.setSearch}
          filteredCompanies={d.filteredCompanies}
          selectedSymbol={d.selectedSymbol}
          pickCompany={d.pickCompany}
          companies={d.companies}
          cmpA={d.cmpA}
          setCmpA={d.setCmpA}
          cmpB={d.cmpB}
          setCmpB={d.setCmpB}
          runCompare={d.runCompare}
          setError={d.setError}
          rangeDays={d.rangeDays}
          gainers={d.gainers}
          losers={d.losers}
        />

        <MainSection
          error={d.error}
          view={d.view}
          setView={d.setView}
          selectedSymbol={d.selectedSymbol}
          priceChart={d.priceChart}
          summary={d.summary}
          compareChart={d.compareChart}
          compareMeta={d.compareMeta}
          compareOptions={d.compareOptions}
        />
      </div>

      <FooterSection />
    </div>
  );
}
