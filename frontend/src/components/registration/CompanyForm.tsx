'use client';

import React from 'react';
import { CompanyInfo } from '../../types/registration';
import { INDIAN_STATES } from '../../data/pricing';
import { Building2, Mail, Phone, FileCheck, MapPin, Globe, User, Briefcase, AlertCircle } from 'lucide-react';

interface CompanyFormProps {
  companyInfo: CompanyInfo;
  onChange: (field: keyof CompanyInfo, value: string) => void;
  errors: Record<string, string>;
}

export const CompanyForm: React.FC<CompanyFormProps> = ({
  companyInfo,
  onChange,
  errors,
}) => {
  return (
    <div className="bg-white rounded-2xl sm:rounded-3xl border border-[#D6E8DE] p-6 sm:p-8 shadow-sm">
      <div className="mb-6 pb-4 border-b border-[#D6E8DE]">
        <h3 className="text-xl font-black text-[#0F172A]">Company Details</h3>
        <p className="text-xs text-slate-500 mt-1">
          Provide your official business identification details for CPCB compliance verification and GST invoicing.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 sm:gap-6">
        {/* Company Name */}
        <div className="md:col-span-2">
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Company Registered Name <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Building2 className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={companyInfo.companyName}
              onChange={(e) => onChange('companyName', e.target.value)}
              placeholder="e.g. EcoPoly Polymer Recyclers Pvt Ltd"
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
                errors.companyName
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.companyName && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.companyName}</span>
            </p>
          )}
        </div>

        {/* Company Email */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Company Email <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Mail className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="email"
              value={companyInfo.companyEmail}
              onChange={(e) => onChange('companyEmail', e.target.value)}
              placeholder="compliance@ecopoly.in"
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
                errors.companyEmail
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.companyEmail && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.companyEmail}</span>
            </p>
          )}
        </div>

        {/* Mobile Number */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Mobile Number <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Phone className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="tel"
              value={companyInfo.mobileNumber}
              onChange={(e) => onChange('mobileNumber', e.target.value)}
              placeholder="9876543210"
              maxLength={10}
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
                errors.mobileNumber
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.mobileNumber && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.mobileNumber}</span>
            </p>
          )}
        </div>

        {/* GST Number */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            GSTIN Number <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <FileCheck className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={companyInfo.gstNumber}
              onChange={(e) => onChange('gstNumber', e.target.value.toUpperCase())}
              placeholder="22AAAAA0000A1Z5"
              maxLength={15}
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none tracking-widest uppercase ${
                errors.gstNumber
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.gstNumber ? (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.gstNumber}</span>
            </p>
          ) : (
            <p className="text-[11px] text-slate-400 mt-1">15-digit GST identification number</p>
          )}
        </div>

        {/* PAN Number */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Company PAN Number <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <FileCheck className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={companyInfo.panNumber}
              onChange={(e) => onChange('panNumber', e.target.value.toUpperCase())}
              placeholder="ABCDE1234F"
              maxLength={10}
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none tracking-widest uppercase ${
                errors.panNumber
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.panNumber ? (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.panNumber}</span>
            </p>
          ) : (
            <p className="text-[11px] text-slate-400 mt-1">10-character alphanumeric PAN</p>
          )}
        </div>

        {/* Factory Address */}
        <div className="md:col-span-2">
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Factory / Facility Address <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <MapPin className="w-5 h-5 absolute left-3.5 top-3.5 text-slate-400" />
            <textarea
              rows={2}
              value={companyInfo.factoryAddress}
              onChange={(e) => onChange('factoryAddress', e.target.value)}
              placeholder="Plot No. 42, GIDC Industrial Estate, Sector 3"
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
                errors.factoryAddress
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.factoryAddress && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.factoryAddress}</span>
            </p>
          )}
        </div>

        {/* State */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            State <span className="text-red-500">*</span>
          </label>
          <select
            value={companyInfo.state}
            onChange={(e) => onChange('state', e.target.value)}
            className={`w-full px-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
              errors.state
                ? 'border-red-500 ring-2 ring-red-100'
                : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
            }`}
          >
            <option value="">Select State</option>
            {INDIAN_STATES.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>
          {errors.state && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.state}</span>
            </p>
          )}
        </div>

        {/* City */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            City <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={companyInfo.city}
            onChange={(e) => onChange('city', e.target.value)}
            placeholder="e.g. Surat / Ahmedabad"
            className={`w-full px-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
              errors.city
                ? 'border-red-500 ring-2 ring-red-100'
                : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
            }`}
          />
          {errors.city && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.city}</span>
            </p>
          )}
        </div>

        {/* Pincode */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Pincode <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={companyInfo.pincode}
            onChange={(e) => onChange('pincode', e.target.value)}
            placeholder="395003"
            maxLength={6}
            className={`w-full px-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
              errors.pincode
                ? 'border-red-500 ring-2 ring-red-100'
                : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
            }`}
          />
          {errors.pincode && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.pincode}</span>
            </p>
          )}
        </div>

        {/* Company Website */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Company Website (Optional)
          </label>
          <div className="relative">
            <Globe className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={companyInfo.companyWebsite}
              onChange={(e) => onChange('companyWebsite', e.target.value)}
              placeholder="https://www.ecopoly.in"
              className="w-full pl-11 pr-4 py-3 rounded-xl border border-[#D6E8DE] text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5] transition-all outline-none"
            />
          </div>
        </div>

        {/* Contact Person */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Authorized Contact Person <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <User className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={companyInfo.contactPerson}
              onChange={(e) => onChange('contactPerson', e.target.value)}
              placeholder="e.g. Rajesh Sharma"
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
                errors.contactPerson
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.contactPerson && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.contactPerson}</span>
            </p>
          )}
        </div>

        {/* Designation */}
        <div>
          <label className="block text-xs font-bold text-[#0F172A] mb-1.5 uppercase tracking-wider">
            Designation <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Briefcase className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={companyInfo.designation}
              onChange={(e) => onChange('designation', e.target.value)}
              placeholder="Head of Sustainability & Compliance"
              className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-medium text-[#0F172A] bg-[#FAFAF8] focus:bg-white transition-all outline-none ${
                errors.designation
                  ? 'border-red-500 ring-2 ring-red-100'
                  : 'border-[#D6E8DE] focus:border-[#0F766E] focus:ring-2 focus:ring-[#ECFDF5]'
              }`}
            />
          </div>
          {errors.designation && (
            <p className="text-xs text-red-500 font-semibold mt-1 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{errors.designation}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
