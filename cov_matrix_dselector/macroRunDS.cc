#include <iostream>
#include <fstream>
#include <string>
#include <chrono>

R__LOAD_LIBRARY(libDSelector.so)

void macroRunDS(){

gEnv->SetValue("ProofLite.Sandbox", "/d/grid15/serwe/UROP/code/tmp");
gROOT->ProcessLine(".x $(ROOT_ANALYSIS_HOME)/scripts/Load_DSelector.C");

TString nameOfTree = "kpkm_Tree";
TChain *chain = new TChain(nameOfTree);

chain->Add( "/lustre0/gluex/ebarriga/KinFitStudy/dataKpKm/tree_kpkm.root" );
DPROOFLiteManager::Process_Chain(chain, "DSelector_kpkm_TSym.C++", 6);

  return;
}
