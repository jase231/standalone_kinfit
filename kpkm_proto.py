#!/usr/bin/env python3

import os
import subprocess
import time


def source_bash_script(script_path):
    """
    Runs a bash script and loads the resulting environment variables
    into the current Python os.environ.
    """
    command = f"source {script_path} && env"

    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, shell=True, executable="/bin/bash"
    )

    for line in proc.stdout:
        # Decode bytes to string
        (key, _, value) = line.decode("utf-8").partition("=")
        # Update python environment
        os.environ[key.strip()] = value.strip()
        print(f"Set {key.strip()} to {value.strip()}")

    proc.communicate()


if __name__ == "__main__":
    # source custom envs to fix -cntr bug
    # source_bash_script("/d/home/serwe/corrected_envs.sh")
    # time.sleep(3)

    import ROOT

    ROOT.gROOT.SetBatch(True)  # do not start an interactive ROOT session

    ROOT.gInterpreter.AddIncludePath("$JANA_HOME/include")
    ROOT.gInterpreter.AddIncludePath("$HALLD_RECON_HOME/$BMS_OSNAME/include")
    # print(f"{ROOT.gInterpreter.GetIncludePath()=}")
    # set search paths for libraries
    ROOT.gSystem.AddDynamicPath("$JANA_HOME/lib")
    ROOT.gSystem.AddDynamicPath("$HALLD_RECON_HOME/$BMS_OSNAME/lib")
    # print(f"{ROOT.gSystem.GetDynamicPath()=}")

    # --- 0. Setup Environment (Paths & Libraries) ---
    # ROOT.gInterpreter.AddIncludePath("/d/grid13/gluex/gluex_top/jana/jana_2.4.3^root6.32.08/Linux_Alma9-x86_64-gcc11.5.0/include")
    # ROOT.gInterpreter.AddIncludePath("/d/grid13/gluex/gluex_top/halld_recon/halld_recon-5.7.0^root6.32.08/Linux_Alma9-x86_64-gcc11.5.0/include")

    # ROOT.gSystem.AddDynamicPath("/d/grid13/gluex/gluex_top/jana/jana_2.4.3^root6.32.08/Linux_Alma9-x86_64-gcc11.5.0/lib")
    # ROOT.gSystem.AddDynamicPath("/d/grid13/gluex/gluex_top/halld_recon/halld_recon-5.7.0^root6.32.08/Linux_Alma9-x86_64-gcc11.5.0/lib")

    # Load the standalone KINFITTER library
    ROOT.gInterpreter.Declare("#define _KINFITTER_STANDALONE_")
    ROOT.gInterpreter.ProcessLine(
        '#include "/d/grid15/serwe/kinfitter/halld_recon/src/libraries/KINFITTER/DKinFitUtils_StandAlone.h"'
    )
    # load in particle enums and helpers
    ROOT.gInterpreter.ProcessLine(
        '#include "/d/grid15/serwe/kinfitter/halld_recon/src/libraries/include/particleType.h"'
    )

    ROOT.gSystem.AddDynamicPath(".")
    assert ROOT.gSystem.Load("./libKINFITTER.so") >= 0, (
        "Could not load './libKINFITTER.so'"
    )

    # get the flat tree
    file = ROOT.TFile("/d/grid15/serwe/kinfitter/kpkm/kpkm_flat_fsym.root")
    tree = file.Get("kpkm")

    # initialize standalone fitter utils with the magnetic field map
    kinFitUtils = ROOT.DKinFitUtils_StandAlone(
        "/lustre0/gluex/ebarriga/KinFitStudy/magneticField/field_map_coarseMesh_111861.msgpack",
        "/lustre0/gluex/ebarriga/KinFitStudy/magneticField/field_map_fineMesh_111861.msgpack",
    )
    kinFitter = ROOT.DKinFitter(kinFitUtils)
    kinFitter.Set_DebugLevel(20)
    full_run = True

    # full stats box
    ROOT.gStyle.SetOptStat(111111)

    # histogram for quantifying differences in chisq_ndf
    c1 = ROOT.TCanvas("c1", "chisq_ndf diff", 800, 600)
    # use log scale
    c1.SetLogy()  # This sets the logarithmic scale
    diff_hist = ROOT.TH1D(
        "chisqdiff",
        "Chi-squared difference;(old_chisq_ndf - refit_chisq_ndf);combos",
        100,
        -70000,
        10000,
    )
    kin_hist = ROOT.TH1D(
        "kindiff",
        "K+ fitted momentum x-component difference;(old_kp_kin.Px() - refit_kp_kin.Px());combos",
        100,
        -1,
        1.2,
    )
    outlier_2d = ROOT.TH2D(
        "outlier_2d",
        "Correlation plot for old-new chisq difference outliers",
        100,
        0,
        10000,
        100,
        0,
        10000,
    )

    # loop over each entry
    for i, entry in enumerate(tree):
        if not full_run and i > 400:
            break

        kinFitter.Reset_NewEvent()

        # lambda for wrapping matrix in shared_ptr as required by fitter
        to_shared = lambda mat: ROOT.std.make_shared[ROOT.TMatrixFSym](mat)

        # get the beam vectors for the current entry
        beam_p4 = entry.beam_p4_meas
        beam_x4 = entry.beam_x4_meas

        # use actual beam covariance matrix
        beam_cov = to_shared(entry.Beam_ErrMatrix)

        # Make_BeamParticle(pid, charge, mass, vertex, momentum, covariance)
        beam_photon = ROOT.Gamma
        beam_part = kinFitUtils.Make_BeamParticle(
            ROOT.PDGtype(beam_photon),
            ROOT.ParticleCharge(beam_photon),
            ROOT.ParticleMass(beam_photon),
            beam_x4,
            beam_p4.Vect(),
            beam_cov,
        )

        # Make_TargetParticle(pid, charge, mass)
        p = ROOT.Proton
        target_part = kinFitUtils.Make_TargetParticle(
            ROOT.PDGtype(p), ROOT.ParticleCharge(p), ROOT.ParticleMass(p)
        )

        # final state kp
        kp_p4 = entry.kp_p4_meas
        kp_x4 = entry.kp_x4_meas
        kp_cov = to_shared(entry.KPlus_ErrMatrix)
        kp = ROOT.KPlus
        kp_part = kinFitUtils.Make_DetectedParticle(
            ROOT.PDGtype(kp),
            ROOT.ParticleCharge(kp),
            ROOT.ParticleMass(kp),
            kp_x4,
            kp_p4.Vect(),
            kp_p4.M(),
            kp_cov,
        )

        # final state km
        km_p4 = entry.km_p4_meas
        km_x4 = entry.km_x4_meas
        km_cov = to_shared(entry.KMinus_ErrMatrix)
        km = ROOT.KMinus
        km_part = kinFitUtils.Make_DetectedParticle(
            ROOT.PDGtype(km),
            ROOT.ParticleCharge(km),
            ROOT.ParticleMass(km),
            km_x4,
            km_p4.Vect(),
            km_p4.M(),
            km_cov,
        )

        # final state recoil proton
        p_p4 = entry.p_p4_meas
        p_x4 = entry.p_x4_meas
        p_cov = to_shared(entry.Proton_ErrMatrix)
        p = ROOT.Proton
        p_part = kinFitUtils.Make_DetectedParticle(
            ROOT.PDGtype(p),
            ROOT.ParticleCharge(p),
            ROOT.ParticleMass(p),
            p_x4,
            p_p4.Vect(),
            p_p4.M(),
            p_cov,
        )

        # create set of the initial particles for momentum constraint
        initial = ROOT.std.set[ROOT.std.shared_ptr[ROOT.DKinFitParticle]]()
        initial.insert(target_part)
        initial.insert(beam_part)
        # create set of final particles for momentum constraint
        final = ROOT.std.set[ROOT.std.shared_ptr[ROOT.DKinFitParticle]]()
        final.insert(kp_part)
        final.insert(km_part)
        final.insert(p_part)

        # create momentum constraint
        p4_const = kinFitUtils.Make_P4Constraint(initial, final)

        # create set for vertex constraint
        vtx_parts = ROOT.std.set[ROOT.std.shared_ptr[ROOT.DKinFitParticle]]()
        vtx_parts.insert(kp_part)
        vtx_parts.insert(km_part)
        vtx_parts.insert(p_part)
        # create set for non-vertex contrained particles
        no_vtx = ROOT.std.set[ROOT.std.shared_ptr[ROOT.DKinFitParticle]]()
        no_vtx.insert(target_part)
        no_vtx.insert(beam_part)
        # create vertex constraint
        vtx_const = kinFitUtils.Make_VertexConstraint(vtx_parts, no_vtx, beam_x4.Vect())

        # run the fit
        kinFitter.Reset_NewFit()
        kinFitter.Add_Constraint(p4_const)
        kinFitter.Add_Constraint(vtx_const)

        # get original kinfit value
        chisq_ndf = entry.kin_chisq / entry.kin_ndf

        success = kinFitter.Fit_Reaction()

        chisq = kinFitter.Get_ChiSq()
        ndf = kinFitter.Get_NDF()
        ndf = ndf if ndf != 0 else 1
        new_chisq_ndf = chisq / ndf
        # moved this into success check
        diff = chisq_ndf - new_chisq_ndf
        # diff_hist.Fill(diff)

        # kinematics diff
        old_kp_px = entry.kp_p4_kin.Px()
        fit_particles = kinFitter.Get_KinFitParticles()
        for j, particle in enumerate(fit_particles):
            if particle.Get_PID() == ROOT.PDGtype(kp):
                refit_kp_p4 = particle.Get_P4()
                refit_kp_px = refit_kp_p4.Px()
                px_diff = old_kp_px - refit_kp_px
                # kin_hist.Fill(px_diff)

        problematic_fits = ROOT.std.vector[ROOT.DKinFitStatus]()

        # check for severity of difference
        if abs(diff) > 2000:
            if chisq_ndf < 200 or new_chisq_ndf < 200:
                # print(f"Extreme chisq difference for event {entry.event}: Old {chisq_ndf}, New {new_chisq_ndf}")
                problematic_fits.push_back(kinFitter.Get_KinFitStatus())
            outlier_2d.Fill(chisq_ndf, new_chisq_ndf)
        if not success:
            print(
                f"Event {entry.event}: Fit Success: {success}, New chisq_ndf: {kinFitter.Get_ChiSq() / ndf}, Old chisq_ndf: {chisq_ndf}"
            )
            # print("--- KMinus_ErrMatrix ---")
            # entry.KMinus_ErrMatrix.Print()
            # print("--- KPlus_ErrMatrix ---")
            # entry.KPlus_ErrMatrix.Print()
            status = kinFitter.Get_KinFitStatus()
            if status == ROOT.d_KinFitFailedSetup:
                print("Setup/validation failed")
            elif status == ROOT.d_KinFitFailedInversion:
                print("Matrix inversion failed")
            elif status == ROOT.d_KinFitTooManyIterations:
                print("Did not converge")
        

        # print(
        #    f"Event {entry.event}: Fit Success: {success}, New chisq_ndf: {kinFitter.Get_ChiSq() / ndf}, Old chisq_ndf: {chisq_ndf}"
        # )
        # )

    diff_hist.Draw()
    c1.Print("plots.pdf(", "pdf")

    kin_hist.Draw()
    c1.Print("plots.pdf", "pdf")

    outlier_2d.Draw()
    c1.Print("plots.pdf)", "pdf")
