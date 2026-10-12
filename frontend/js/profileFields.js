/* Profile option lists and the payload sent to the server. */

export const STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana',
  'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
  'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Andaman and Nicobar Islands', 'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry',
];
export const CATEGORIES = ['General', 'OBC', 'SC', 'ST', 'EWS'];
export const EDUCATION = [
  ['9th', '9th', '9वीं'], ['10th', '10th', '10वीं'], ['11th', '11th', '11वीं'], ['12th', '12th', '12वीं'],
  ['Diploma', 'Diploma', 'डिप्लोमा'], ['Undergraduate', 'Undergraduate (college degree)', 'स्नातक (कॉलेज डिग्री)'],
  ['Postgraduate', 'Postgraduate (master’s)', 'स्नातकोत्तर (मास्टर्स)'],
];

export const EXAMPLE = {
  name: 'Aisha Kumar', age: 21, gender: 'Female', state: 'Karnataka', category: 'OBC',
  education_level: 'Undergraduate', field_of_study: 'Engineering', annual_income: 300000,
  disability: false, goals: 'Finish B.Tech and later start a company',
};

export function profilePayload(p) {
  const keys = ['name', 'age', 'gender', 'state', 'category', 'education_level', 'field_of_study', 'annual_income', 'disability', 'goals'];
  return Object.fromEntries(keys.map((k) => [k, p[k] ?? (k === 'disability' ? false : null)]));
}
