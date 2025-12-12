import { useState } from 'react';
import { Building2, Users, Mail, Search } from 'lucide-react';
import { useCompanies } from '../hooks/useEmailIntel';
import type { Company } from '../types';

// Health score to color
function healthToColor(score: number): string {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#eab308';
  if (score >= 40) return '#f97316';
  return '#ef4444';
}

function healthToLabel(score: number): string {
  if (score >= 80) return '优秀';
  if (score >= 60) return '良好';
  if (score >= 40) return '一般';
  return '需关注';
}

const relationTypeLabels: Record<string, { label: string; color: string }> = {
  client: { label: '客户', color: 'bg-green-500/20 text-green-400' },
  vendor: { label: '供应商', color: 'bg-blue-500/20 text-blue-400' },
  partner: { label: '合作伙伴', color: 'bg-purple-500/20 text-purple-400' },
  government: { label: '政府机构', color: 'bg-amber-500/20 text-amber-400' },
  internal: { label: '内部', color: 'bg-orange-500/20 text-orange-400' },
  unknown: { label: '未分类', color: 'bg-zinc-500/20 text-zinc-400' },
};

function CompanyCard({ company, onClick, isSelected }: {
  company: Company;
  onClick: () => void;
  isSelected: boolean;
}) {
  const relType = relationTypeLabels[company.relation_type] || relationTypeLabels.unknown;

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border cursor-pointer transition-all ${
        isSelected
          ? 'bg-orange-500/10 border-orange-500/30'
          : 'bg-zinc-900/30 border-zinc-800 hover:border-zinc-700'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-zinc-400" />
          </div>
          <div>
            <h4 className="text-white font-medium">{company.name}</h4>
            <span className={`text-xs px-2 py-0.5 rounded ${relType.color}`}>
              {relType.label}
            </span>
          </div>
        </div>
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: healthToColor(company.health_score) }}
          title={`健康度: ${company.health_score}%`}
        />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="bg-zinc-800/50 rounded p-2">
          <div className="text-lg font-semibold text-white">{company.total_emails}</div>
          <div className="text-xs text-zinc-500">总邮件</div>
        </div>
        <div className="bg-zinc-800/50 rounded p-2">
          <div className="text-lg font-semibold text-white">{company.contact_count}</div>
          <div className="text-xs text-zinc-500">联系人</div>
        </div>
        <div className="bg-zinc-800/50 rounded p-2">
          <div className="text-lg font-semibold text-white">{company.emails_30d}</div>
          <div className="text-xs text-zinc-500">近30天</div>
        </div>
      </div>
    </div>
  );
}

function CompanyDetail({ company }: { company: Company }) {
  const relType = relationTypeLabels[company.relation_type] || relationTypeLabels.unknown;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-zinc-800 flex items-center justify-center">
            <Building2 className="w-7 h-7 text-zinc-400" />
          </div>
          <div>
            <h3 className="text-xl font-semibold text-white">{company.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs px-2 py-0.5 rounded ${relType.color}`}>
                {relType.label}
              </span>
              {company.domains.map(d => (
                <span key={d} className="text-xs text-zinc-500">{d}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Health Score */}
      <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
        <h4 className="text-sm font-medium text-zinc-400 mb-3">关系健康度</h4>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${company.health_score}%`,
                  backgroundColor: healthToColor(company.health_score),
                }}
              />
            </div>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold text-white">{company.health_score}%</span>
            <span className="text-sm text-zinc-500 ml-2">{healthToLabel(company.health_score)}</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
          <div className="flex items-center gap-2 text-zinc-400 mb-2">
            <Mail className="w-4 h-4" />
            <span className="text-sm">邮件往来</span>
          </div>
          <div className="text-2xl font-bold text-white">{company.total_emails}</div>
          <div className="text-xs text-zinc-500">近30天: {company.emails_30d} 封</div>
        </div>
        <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
          <div className="flex items-center gap-2 text-zinc-400 mb-2">
            <Users className="w-4 h-4" />
            <span className="text-sm">联系人</span>
          </div>
          <div className="text-2xl font-bold text-white">{company.contact_count}</div>
          <div className="text-xs text-zinc-500">活跃联系人</div>
        </div>
      </div>

      {/* Contacts */}
      {company.contacts && company.contacts.length > 0 && (
        <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
          <h4 className="text-sm font-medium text-zinc-400 mb-3">关键联系人</h4>
          <div className="space-y-3">
            {company.contacts.slice(0, 5).map((contact) => (
              <div key={contact.id} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-sm text-zinc-400">
                    {contact.name[0]}
                  </div>
                  <div>
                    <p className="text-sm text-white">{contact.name}</p>
                    <p className="text-xs text-zinc-500">{contact.email}</p>
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: healthToColor(contact.health_score) }}
                  />
                  <span className="text-xs text-zinc-500 ml-2">{contact.total_emails} 封</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline placeholder */}
      <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
        <h4 className="text-sm font-medium text-zinc-400 mb-3">沟通时间线</h4>
        <div className="h-24 flex items-center justify-center text-zinc-600 text-sm">
          时间线图表 (待实现)
        </div>
      </div>
    </div>
  );
}

export default function CompanyIntel() {
  const { data: companies, isLoading } = useCompanies();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [filterType, setFilterType] = useState<string>('all');

  // Filter companies
  let filteredCompanies = companies || [];
  if (searchQuery) {
    filteredCompanies = filteredCompanies.filter(c =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.domains.some(d => d.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  }
  if (filterType !== 'all') {
    filteredCompanies = filteredCompanies.filter(c => c.relation_type === filterType);
  }

  // Sort by email count
  filteredCompanies = [...filteredCompanies].sort((a, b) => b.total_emails - a.total_emails);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Company Intelligence</h2>
        <p className="text-sm text-zinc-500 mt-1">公司画像与关系分析</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="搜索公司..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-orange-500"
        >
          <option value="all">全部类型</option>
          <option value="client">客户</option>
          <option value="vendor">供应商</option>
          <option value="partner">合作伙伴</option>
          <option value="government">政府机构</option>
        </select>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex gap-6 min-h-0">
        {/* Company List */}
        <div className="w-1/2 overflow-auto pr-2 space-y-3">
          {filteredCompanies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              onClick={() => setSelectedCompany(company)}
              isSelected={selectedCompany?.id === company.id}
            />
          ))}
          {filteredCompanies.length === 0 && (
            <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
              <Building2 className="w-12 h-12 mb-4 opacity-50" />
              <p>暂无公司数据</p>
            </div>
          )}
        </div>

        {/* Company Detail */}
        <div className="w-1/2 overflow-auto pl-2">
          {selectedCompany ? (
            <CompanyDetail company={selectedCompany} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500">
              <Building2 className="w-16 h-16 mb-4 opacity-30" />
              <p>选择一家公司查看详情</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
